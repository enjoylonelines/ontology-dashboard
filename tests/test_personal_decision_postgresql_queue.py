"""Disposable PostgreSQL integration checks for the decision work queue."""
import os
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import pytest

from app.infra.db.decision_run_repository import DecisionRunRepository
from app.operations.decision_durable_runner import DurableDecisionRunner, configuration_binding
from app.operations.decision_policy import decision_policy_facts_from_packet
from app.operations.decision_session_service import DecisionSessionApplicationService, _packet_binding
from app.operations.decision_support_agent import DecisionAgentRequest
from tests.test_decision_session_service import IDENTITY, agent_factory, packet




def test_postgresql_pending_not_hidden_by_completed_limit(pg_store):
    """A page of completed runs must not hide a later unfinished run."""
    import json
    prefix = uuid4().hex[:16]
    scope = pg_store.scope("unused", IDENTITY)
    with pg_store.connection(IDENTITY) as connection:
        for i in range(56):
            session_id = f"DS-scan-{prefix}-{i:02d}"
            state = {"result": {"completed": True}} if i < 55 else {"result": None}
            pg_store.execute(
                connection,
                "INSERT INTO decision_agent_runs "
                "(decision_session_id,organization_id,project_id,identity_hash,binding,state_json,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (session_id, *scope[1:], "fixture", json.dumps(state), float(i + 1)),
            )
    pending = pg_store.list_pending(IDENTITY, limit=50)
    assert any(sid == f"DS-scan-{prefix}-55" for sid, _ in pending)



def test_postgresql_expired_lease_reclaimed_and_stale_owner_fenced(pg_store):
    """Crash model: old process holds a lease, expires, replacement takes ownership."""
    from app.operations.decision_run_store import DecisionRunBusy, DecisionRunLeaseLost
    from time import sleep
    identity = IDENTITY.model_copy(update={"asset_id": f"LEASE-{uuid4().hex[:12]}"})
    old = DecisionRunRepository(pg_store.database, lease_seconds=0.3)
    new = DecisionRunRepository(pg_store.database, lease_seconds=2)
    sid = f"DS-lease-{uuid4().hex[:16]}"
    initial = {"result": None, "stage": "started"}
    _, first = old.claim(sid, identity, "fixture-binding", initial)
    assert first
    with pytest.raises(DecisionRunBusy):
        new.claim(sid, identity, "fixture-binding", initial)
    sleep(0.5)
    _, second = new.claim(sid, identity, "fixture-binding", initial)
    assert second and second != first
    with pytest.raises(DecisionRunLeaseLost):
        old.save(sid, identity, first, {"result": {"stale": True}})
    with pytest.raises(DecisionRunLeaseLost):
        old.heartbeat(sid, identity, first)
    new.save(sid, identity, second, {"result": {"owner": "replacement"}})
    assert new.load(sid, identity)["result"] == {"owner": "replacement"}

@pytest.fixture
def pg_store():
    dsn = os.getenv("DECISION_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("requires isolated migrated DECISION_TEST_POSTGRES_DSN")
    return DecisionRunRepository(dsn)


def test_postgresql_concurrent_duplicate_requests(pg_store):
    service = DecisionSessionApplicationService(packet, agent_factory, pg_store)
    request_id = f"postgres-{uuid4().hex[:16]}"
    try:
        with ThreadPoolExecutor(max_workers=10) as clients:
            rows = list(clients.map(
                lambda _: service.enqueue(identity=IDENTITY, actor_role="process_engineer", request_id=request_id, actor_id="pg-test"),
                range(20),
            ))
        assert len({sid for sid, _, _ in rows}) == 1
        for _, handle, _ in rows:
            if handle:
                handle.future.result(timeout=60)
        assert pg_store.load(rows[0][0], IDENTITY)["result"] is not None
    finally:
        service.stop_workers(wait=True)


def test_postgresql_100_undispatched_resumed(pg_store):
    identities = [IDENTITY.model_copy(update={"asset_id": f"PG-CNC-{i:03d}"}) for i in range(100)]
    ids = []
    prefix = uuid4().hex[:12]
    for i, identity in enumerate(identities):
        request = DecisionAgentRequest(identity=identity, actor_role="process_engineer", policy_facts=decision_policy_facts_from_packet(packet(identity)))
        agent = agent_factory(identity)
        binding = _packet_binding(packet(identity))
        initial = DurableDecisionRunner.initial_state(request, evidence_binding=binding)
        initial["created_at"] = agent.now().isoformat()
        sid = f"DS-pg-{prefix}-{i:03d}"
        _, token = pg_store.claim(sid, identity, sha256((configuration_binding(agent, request) + binding).encode()).hexdigest(), initial)
        assert token
        pg_store.release(sid, identity, token)
        ids.append(sid)
    fresh = DecisionSessionApplicationService(packet, agent_factory, pg_store)
    try:
        with ThreadPoolExecutor(max_workers=10) as clients:
            groups = list(clients.map(lambda identity: fresh.resume_pending(identity=identity), identities))
        for handles in groups:
            for handle in handles:
                handle.future.result(timeout=60)
        assert all(pg_store.load(sid, identity).get("result") is not None for sid, identity in zip(ids, identities))
    finally:
        fresh.stop_workers(wait=True)
