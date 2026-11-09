# DecisionSession Kubernetes worker alignment — 2026-11-05

## Observed problem
The existing `ontology-dashboard-workers` Deployment runs `ontology_dashboard.worker` (outbox automation), not the DecisionSession resumer. The API starts its own resumer if `DECISION_RESUMER_IDENTITIES` is present.

## Scope and change
- Added `infra/production/decision-workers.yaml` for a distinct DecisionSession Deployment using `python -m app.operations.decision_worker_process`.
- Added it to the production Kustomization; preserved the existing outbox worker.
- Explicitly disabled the API's identity-based resumer in its Kubernetes environment, so the shared Secret cannot accidentally enable duplicate polling in the API.
- Worker requires a real `DECISION_RESUMER_IDENTITIES` JSON array in `ontology-dashboard-secrets`; no real tenant identities were fabricated.
- Two replicas and 60s termination grace are **initial configuration**, not measured scaling or shutdown guarantees.

## Evidence
- YAML documents parsed and structural assertions for the worker entrypoint, Secret key and API separation passed.
- `git diff --check` passed.
- Prior regression run: 8 passed, 2 skipped; PostgreSQL integration cases skipped without isolated DSN.
- Docker available; `kind`, `k3d`, `kubectl` were not on PATH. No cluster, KEDA, HPA or real Pod recovery run.

## Outstanding risks / gates
1. Confirm container image includes the untracked `decision_worker_process.py` when built; a pre-existing registry image will not necessarily contain it.
2. Verify the identity provider's static list matches permitted tenants; the current per-identity scan is not a global priority claim and can starve pending work behind completed rows.
3. Verify independent-process PostgreSQL claim/lease/fencing under SIGKILL and lease expiry, including in-flight work.
4. Confirm API inline supervisor behavior separately: disabling the API resumer does not disable its existing inline supervisor.
5. Validate SIGTERM graceful shutdown and no new work after shutdown begins; 60s grace is only a configured timeout.
6. Deploy to isolated local kind/k3d with test Secret, test DB and deterministic LLM; then measure Pod recreation, queue wait and scale up/down.
7. Priority Critical/Normal and KEDA are not implemented by this alignment change.

Human hypothesis/prediction: unrecorded. Final human adoption decision and changed belief: pending.
