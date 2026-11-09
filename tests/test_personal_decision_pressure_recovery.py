"""Synthetic duplicate-submit and persisted-before-dispatch recovery experiments."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import pytest

from app.infra.db.migrations import migrate
from app.infra.db.decision_run_repository import DecisionRunRepository
from app.operations.decision_durable_runner import DurableDecisionRunner, configuration_binding
from app.operations.decision_policy import decision_policy_facts_from_packet
from app.operations.decision_session_service import DecisionSessionApplicationService, _packet_binding
from app.operations.decision_support_agent import DecisionAgentRequest
from tests.test_decision_session_service import IDENTITY, agent_factory, packet


@pytest.mark.parametrize("count", [10, 30, 100])
def test_distinct_asset_burst_repeated(tmp_path: Path, count: int):
    timings = []
    for repeat in range(3):
        db = tmp_path / f"burst-{count}-{repeat}.db"
        migrate(str(db))
        service = DecisionSessionApplicationService(packet, agent_factory, DecisionRunRepository(db))
        identities = [IDENTITY.model_copy(update={"asset_id": f"CNC-{i:03d}"}) for i in range(count)]
        start = perf_counter()
        try:
            def submit(i):
                return i, service.enqueue(identity=identities[i], actor_role="process_engineer", request_id=f"repeat-{repeat}-{i:03d}", actor_id="burst")
            with ThreadPoolExecutor(max_workers=10) as clients:
                rows = list(clients.map(submit, range(count)))
            enqueue_elapsed = perf_counter() - start
            ids = set()
            for i, (sid, handle, done) in rows:
                result = done if done is not None else handle.future.result(timeout=60)
                assert result.session.identity.asset_id == identities[i].asset_id
                ids.add(sid)
                assert service.get(decision_session_id=sid, identity=identities[i]) is not None
            assert len(ids) == count
            elapsed = perf_counter() - start
            timings.append((round(enqueue_elapsed, 3), round(elapsed, 3)))
        finally:
            service.stop_workers(wait=True)
    print(f"burst_count={count} repeats=3 enqueue_and_total_seconds={timings}")


def test_same_request_concurrent_retries_converge_to_one_persisted_run(tmp_path: Path):
    db = tmp_path / "duplicates.db"
    migrate(str(db))
    service = DecisionSessionApplicationService(packet, agent_factory, DecisionRunRepository(db))
    try:
        def submit(_):
            return service.enqueue(identity=IDENTITY, actor_role="process_engineer", request_id="same-request-001", actor_id="same-user")
        with ThreadPoolExecutor(max_workers=10) as clients:
            rows = list(clients.map(submit, range(20)))
        assert len({sid for sid, _, _ in rows}) == 1
        assert len({handle.job_id for _, handle, _ in rows if handle is not None}) <= 1
        for sid, handle, completed in rows:
            if handle is not None:
                handle.future.result(timeout=60)
        sid = rows[0][0]
        state = service.run_store.load(sid, IDENTITY)
        assert state is not None and state.get("result") is not None
        assert service.get(decision_session_id=sid, identity=IDENTITY) is not None
        print(f"duplicate_requests=20 distinct_session_ids=1 completed_state=1 unique_dispatched_jobs={len({h.job_id for _,h,_ in rows if h is not None})}")
    finally:
        service.stop_workers(wait=True)


def test_100_persisted_before_dispatch_are_resumed_by_fresh_service(tmp_path: Path):
    db = tmp_path / "undispatched.db"
    migrate(str(db))
    store = DecisionRunRepository(db)
    identities = [IDENTITY.model_copy(update={"asset_id": f"CNC-{i:03d}"}) for i in range(100)]
    session_ids = []
    for i, identity in enumerate(identities):
        request = DecisionAgentRequest(identity=identity, actor_role="process_engineer", policy_facts=decision_policy_facts_from_packet(packet(identity)))
        agent = agent_factory(identity)
        binding = _packet_binding(packet(identity))
        initial = DurableDecisionRunner.initial_state(request, evidence_binding=binding)
        initial["created_at"] = agent.now().isoformat()
        sid = f"DS-undispatched-{i:03d}"
        _, token = store.claim(sid, identity, sha256((configuration_binding(agent, request) + binding).encode()).hexdigest(), initial)
        assert token is not None
        store.release(sid, identity, token)
        session_ids.append(sid)
    fresh = DecisionSessionApplicationService(packet, agent_factory, DecisionRunRepository(db))
    start = perf_counter()
    try:
        # Explicit scope-based resumption, not a proof of automatic lifecycle discovery.
        with ThreadPoolExecutor(max_workers=10) as clients:
            handles = list(clients.map(lambda identity: fresh.resume_pending(identity=identity), identities))
        for group in handles:
            for handle in group:
                handle.future.result(timeout=60)
        for sid, identity in zip(session_ids, identities):
            state = fresh.run_store.load(sid, identity)
            assert state is not None and state.get("result") is not None
        print(f"undispatched=100 recovered=100 elapsed_seconds={perf_counter()-start:.3f}")
    finally:
        fresh.stop_workers(wait=True)


def test_100_persisted_jobs_auto_resume_on_fresh_service_start(tmp_path: Path):
    import time
    db = tmp_path / "auto-resume.db"
    migrate(str(db))
    store = DecisionRunRepository(db)
    identities = [IDENTITY.model_copy(update={"asset_id": f"AUTO-CNC-{i:03d}"}) for i in range(100)]
    ids = []
    for i, identity in enumerate(identities):
        request = DecisionAgentRequest(identity=identity, actor_role="process_engineer", policy_facts=decision_policy_facts_from_packet(packet(identity)))
        agent = agent_factory(identity)
        binding = _packet_binding(packet(identity))
        initial = DurableDecisionRunner.initial_state(request, evidence_binding=binding)
        initial["created_at"] = agent.now().isoformat()
        sid = f"DS-auto-{i:03d}"
        _, token = store.claim(sid, identity, sha256((configuration_binding(agent, request) + binding).encode()).hexdigest(), initial)
        assert token
        store.release(sid, identity, token)
        ids.append(sid)

    fresh = DecisionSessionApplicationService(packet, agent_factory, DecisionRunRepository(db))
    fresh.start_resumer(identity_provider=lambda: identities, interval_seconds=0.1)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            recovered = sum(fresh.run_store.load(sid, identity).get("result") is not None for sid, identity in zip(ids, identities))
            if recovered == 100:
                break
            time.sleep(0.1)
        assert recovered == 100, f"automatic scoped resumer recovered {recovered}/100"
        print(f"configured_identity_auto_resumer_recovered={recovered}/100")
    finally:
        fresh.stop_workers(wait=True)


def test_repeated_resumer_ticks_do_not_dispatch_duplicate_jobs(tmp_path: Path):
    db = tmp_path / "resumer-ticks.db"
    migrate(str(db))
    identity = IDENTITY.model_copy(update={"asset_id": "TICK-CNC-001"})
    store = DecisionRunRepository(db)
    request = DecisionAgentRequest(identity=identity, actor_role="process_engineer", policy_facts=decision_policy_facts_from_packet(packet(identity)))
    agent = agent_factory(identity)
    binding = _packet_binding(packet(identity))
    initial = DurableDecisionRunner.initial_state(request, evidence_binding=binding)
    initial["created_at"] = agent.now().isoformat()
    sid = "DS-tick-dedup-001"
    _, token = store.claim(sid, identity, sha256((configuration_binding(agent, request) + binding).encode()).hexdigest(), initial)
    store.release(sid, identity, token)
    service = DecisionSessionApplicationService(packet, agent_factory, store)
    try:
        first = service.resume_pending(identity=identity)
        second = service.resume_pending(identity=identity)
        assert len(first) == 1
        assert len(second) <= 1
        if second:
            assert first[0].job_id == second[0].job_id
        first[0].future.result(timeout=30)
        assert store.load(sid, identity)["result"] is not None
    finally:
        service.stop_workers(wait=True)


def test_dedicated_worker_requires_explicit_scopes(monkeypatch):
    from app.operations import decision_worker_process
    class UnscopedService:
        pending_identity_provider = None
    monkeypatch.setattr(decision_worker_process, "get_decision_session_service", lambda: UnscopedService())
    with pytest.raises(RuntimeError, match="DECISION_RESUMER_IDENTITIES"):
        decision_worker_process.run()
