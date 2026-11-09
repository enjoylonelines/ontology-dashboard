"""Bounded synthetic 100-asset DecisionSession burst; not a live event-ingestion benchmark."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

from app.infra.db.migrations import migrate
from app.infra.db.decision_run_repository import DecisionRunRepository
from app.operations.decision_session_service import DecisionSessionApplicationService
from tests.test_decision_session_service import IDENTITY, agent_factory, packet


def test_100_distinct_asset_decision_sessions_are_persisted_without_cross_asset_mixup(tmp_path: Path):
    database = tmp_path / "100-asset-decision-burst.db"
    migrate(str(database))
    store = DecisionRunRepository(database)
    service = DecisionSessionApplicationService(packet_loader=packet, agent_factory=agent_factory, run_store=store)
    identities = [
        IDENTITY.model_copy(update={"asset_id": f"CNC-{index:03d}"})
        for index in range(100)
    ]
    started = perf_counter()
    try:
        def submit(index: int):
            identity = identities[index]
            session_id, handle, completed = service.enqueue(
                identity=identity,
                actor_role="process_engineer",
                request_id=f"asset-burst-{index:03d}",
                actor_id="load-test",
            )
            return index, session_id, handle, completed

        with ThreadPoolExecutor(max_workers=10) as clients:
            submitted = [future.result(timeout=60) for future in as_completed(
                [clients.submit(submit, index) for index in range(100)]
            )]
        enqueue_seconds = perf_counter() - started
        for index, session_id, handle, completed in submitted:
            result = completed if completed is not None else handle.future.result(timeout=60)
            assert result.session.decision_session_id == session_id
            assert result.session.identity.asset_id == identities[index].asset_id
        completed_seconds = perf_counter() - started

        assert len({session_id for _, session_id, _, _ in submitted}) == 100
        for index, session_id, _, _ in submitted:
            loaded = service.get(decision_session_id=session_id, identity=identities[index])
            assert loaded is not None
            assert loaded.identity.asset_id == identities[index].asset_id
            wrong = identities[(index + 1) % 100]
            assert service.get(decision_session_id=session_id, identity=wrong) is None
        print(
            f"100_asset_burst enqueue_seconds={enqueue_seconds:.3f} "
            f"completion_seconds={completed_seconds:.3f} "
            f"submit_concurrency=10 worker_count=2 persisted=100"
        )
    finally:
        service.stop_workers(wait=True)
