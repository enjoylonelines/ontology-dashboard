"""Reproducible synthetic PostgreSQL DecisionSession DB-queue load benchmark.

Run against a disposable migrated PostgreSQL database only:
DECISION_TEST_POSTGRES_DSN=... python -m tests.personal_decision_queue_load
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

from app.infra.db.decision_run_repository import DecisionRunRepository
from app.operations.decision_session_service import DecisionSessionApplicationService
from app.operations.decision_worker import DecisionWorkerSupervisor
from tests.test_decision_session_service import IDENTITY, agent_factory, packet


def percentile(values, fraction):
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))], 4)


def run():
    dsn = os.environ["DECISION_TEST_POSTGRES_DSN"]
    if "127.0.0.1" not in dsn and "localhost" not in dsn:
        raise RuntimeError("load benchmark requires loopback disposable PostgreSQL")
    counts = (100, 500, 1000)
    results = []
    for count in counts:
        for workers in (2, 4):
            store = DecisionRunRepository(dsn)
            service = DecisionSessionApplicationService(packet, agent_factory, store, worker_supervisor=DecisionWorkerSupervisor(max_workers=workers))
            prefix = uuid4().hex[:10]
            identities = [IDENTITY.model_copy(update={"asset_id": f"LOAD-{prefix}-{i:04d}"}) for i in range(count)]
            submitted = {}
            start = perf_counter()
            try:
                def enqueue(i):
                    before = perf_counter()
                    sid, handle, completed = service.enqueue(identity=identities[i], actor_role="process_engineer", request_id=f"load-{prefix}-{i:04d}", actor_id="load-test")
                    submitted[i] = (sid, handle, completed, perf_counter(), before)
                with ThreadPoolExecutor(max_workers=10) as clients:
                    list(clients.map(enqueue, range(count)))
                enqueue_end = perf_counter()
                for i in range(count):
                    sid, handle, completed, _, _ = submitted[i]
                    if handle:
                        handle.future.result(timeout=180)
                done = perf_counter()
                missing = sum(store.load(submitted[i][0], identities[i]).get("result") is None for i in range(count))
                enqueue_latencies = [(v[3] - v[4]) * 1000 for v in submitted.values()]
                result = {
                    "count": count, "workers": workers,
                    "enqueue_seconds": round(enqueue_end - start, 3),
                    "all_complete_seconds": round(done - start, 3),
                    "throughput_per_second": round(count / (done - start), 2),
                    "enqueue_latency_p50_ms": percentile(enqueue_latencies, 0.5),
                    "enqueue_latency_p95_ms": percentile(enqueue_latencies, 0.95),
                    "missing_results": missing,
                    "synthetic": True,
                    "note": "enqueue latency is not queue-wait; completion includes sequential future inspection",
                }
                print(json.dumps(result), flush=True)
                results.append(result)
                assert missing == 0
            finally:
                service.stop_workers(wait=True)
    output = Path("docs/evidence/2026-11-05-personal-postgres-load-results.json")
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(f"saved={output}")


if __name__ == "__main__":
    run()
