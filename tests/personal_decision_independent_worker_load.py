"""Synthetic PostgreSQL independent-process polling, SIGKILL/restart and paced-arrival benchmark."""
import json
import os
import signal
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from app.infra.db.decision_run_repository import DecisionRunRepository
from app.operations.decision_durable_runner import DurableDecisionRunner, configuration_binding
from app.operations.decision_policy import decision_policy_facts_from_packet
from app.operations.decision_session_service import _packet_binding
from app.operations.decision_support_agent import DecisionAgentRequest
from tests.test_decision_session_service import IDENTITY, agent_factory, packet


def percentile(items, p):
    items = sorted(items)
    return round(items[min(len(items)-1, int((len(items)-1)*p))], 4)


def main():
    dsn = os.environ["DECISION_TEST_POSTGRES_DSN"]
    if "127.0.0.1" not in dsn and "localhost" not in dsn:
        raise RuntimeError("isolated loopback PostgreSQL required")
    count = int(os.getenv("DECISION_LOAD_COUNT", "100"))
    rate = float(os.getenv("DECISION_LOAD_RATE", "20"))
    if not 1 <= count <= 500 or not 1 <= rate <= 100:
        raise ValueError("bounded synthetic benchmark only")
    store = DecisionRunRepository(dsn, lease_seconds=3)
    prefix = uuid4().hex[:8]
    identities = [IDENTITY.model_copy(update={"asset_id": f"PACE-{prefix}-{i:04d}"}) for i in range(count)]
    ids = []
    env = os.environ.copy()
    env["DECISION_LOAD_ASSETS"] = json.dumps([i.asset_id for i in identities])
    env["DECISION_LOAD_POLL_SECONDS"] = "0.1"
    env["DECISION_LOAD_LEASE_SECONDS"] = "3"

    def worker():
        return subprocess.Popen([sys.executable, "-m", "tests.personal_decision_worker_harness"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def stop(proc, hard=False):
        if proc.poll() is None:
            proc.kill() if hard else proc.terminate()
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()

    process = None
    start = monotonic()
    try:
        process = worker()
        for i, identity in enumerate(identities):
            request = DecisionAgentRequest(identity=identity, actor_role="process_engineer", policy_facts=decision_policy_facts_from_packet(packet(identity)))
            agent = agent_factory(identity)
            binding = _packet_binding(packet(identity))
            initial = DurableDecisionRunner.initial_state(request, evidence_binding=binding)
            initial["created_at"] = agent.now().isoformat()
            sid = f"DS-paced-{prefix}-{i:04d}"
            _, token = store.claim(sid, identity, sha256((configuration_binding(agent, request)+binding).encode()).hexdigest(), initial)
            assert token
            store.release(sid, identity, token)
            ids.append(sid)
            target = start + (i+1)/rate
            if monotonic() < target:
                sleep(target-monotonic())
        submitted = monotonic()
        # Kill first worker mid-flight or after early completions; restart a fresh process.
        stop(process, hard=True)
        killed_at = monotonic()
        process = worker()
        completed_at = {}
        deadline = monotonic()+90
        while monotonic() < deadline and len(completed_at) < count:
            for i, identity in enumerate(identities):
                if i not in completed_at and store.load(ids[i], identity).get("result") is not None:
                    completed_at[i] = monotonic()
            if len(completed_at) < count:
                sleep(0.1)
        elapsed = monotonic()
        assert len(completed_at) == count, f"completed {len(completed_at)}/{count}"
        observed_completion = [(completed_at[i]-(start+(i+1)/rate))*1000 for i in range(count)]
        result = {
            "count": count, "target_arrival_rate_per_second": rate,
            "producer_elapsed_seconds": round(submitted-start, 3),
            "all_complete_elapsed_seconds": round(elapsed-start, 3),
            "restart_to_all_complete_seconds": round(elapsed-killed_at, 3),
            "completed": len(completed_at), "missing": count-len(completed_at),
            "observed_end_to_end_p50_ms": percentile(observed_completion, .5),
            "observed_end_to_end_p95_ms": percentile(observed_completion, .95),
            "notes": "Synthetic fixture, external OS process SIGKILL/restart; observed completion is polling upper bound, NOT queue-wait. No API, LLM or sustained long-run DB metrics.",
        }
        print(json.dumps(result), flush=True)
        Path("docs/evidence/2026-11-05-personal-independent-worker-load.json").write_text(json.dumps(result, indent=2)+"\n")
    finally:
        if process is not None:
            stop(process)


if __name__ == "__main__":
    main()
