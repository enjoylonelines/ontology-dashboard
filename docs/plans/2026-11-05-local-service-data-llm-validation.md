# Local service / data / LLM validation — active slice (2026-11-05)

## Problem and decision boundary
Goal stated by user: validate real local service operation, failure recovery, worker scaling and LLM improvements, while auditing DB schema and sensor data and reducing unnecessary complexity.
Human hypothesis / quantitative prediction: unrecorded. Human architecture adoption decision: pending.
No production DB, actual LLM calls, remote deployment, or destructive schema changes in this slice.

## Observed repository facts
- `infra/macmini/docker-compose.yml` already defines PostgreSQL, Redis, Backend, Frontend, live-ingestor and one-shot Generator; it is a **different runtime** from `infra/production` Kubernetes manifests.
- Canonical sensor sources are compressor/CNC observations; bundle ingestion maps to `pm_compressor_observations` and `pm_cnc_observations`, while runtime overlay observations have a separate source.
- `decision_agent_runs` persists state JSON, identity hash, binding, lease owner and expiry; the current `list_pending` applies the completed-result filter *after* a limited SQL query, risking starvation.
- API `DecisionSessionApplicationService.enqueue` starts an in-process supervisor; a dedicated resumer process exists separately.
- Existing Outbox delivers Maintenance replay events, not DecisionSession briefings. The Kubernetes outbox command is not proven runnable from current backend source.
- A prior local briefing run validated real LLM creation and readback, but recorded an evidence gap: saved inspection history was absent from a FILE event packet. This is a content-quality blocker, not provider connectivity.
- Existing Compose Redis is used for distributed rate limiting, not as a DecisionSession message broker. Do not remove without rate-limit regression tests.

## Target isolated validation topology
Sensor fixture/replay -> validated observation ingest -> PostgreSQL (canonical, overlay, event, decision runs) -> FastAPI enqueue/read -> independent DecisionSession workers -> deterministic/LLM briefing -> persisted readback.
Local kind/k3d + KEDA is a **later** execution environment for the same isolated DB and workers; start with Compose and prove data correctness first. Exclude Generator retraining and Outbox from the initial DecisionSession experiment unless a fixture requires them.

## Gates and experiments
### Gate A — database schema and lineage
1. Inventory migrations, keys/indexes/partitioning/RLS and relationships for assets, compressor/CNC observations, overlay, prediction results, events, snapshots, decision runs, and outbox.
2. Isolated PostgreSQL migration and schema introspection: required uniqueness, tenant/project isolation, timestamp units/time zones, FK or validated logical relationships, index plans.
3. Reproduce completed-row starvation in `list_pending` (50+ completed rows before pending), then propose minimal DB-level filtering/claim change. Test multi-process claim/fencing and expiry.
4. Validate latest snapshot binding and immutable evidence references; no stale result overwrites.
Exit: reproducible migration, no cross-tenant reads, no lost/duplicated final results.

### Gate B — sensor data and runtime replay
1. Inventory provenance: generated vs public canonical vs synthetic; never describe fixtures as live industrial telemetry.
2. Check schema, sampling interval, ordering, duplicate (asset_id, observed_at), missing/null values, sensor units, operating state, outliers, drift, late/out-of-order events.
3. Preserve separate failure truth and prevent training/evaluation label leakage into runtime inference.
4. Replay 100/500/1000 assets at 10-second watch cycles with 1/10/50% change; distinguish 10-second *watch* cadence from canonical sensor sampling cadence.
5. Check prediction -> event -> evidence snapshot -> decision briefing lineage, no missing Critical event, and coalescing only where allowed.
Exit: integrity report with counts and violations by source/fixture.

### Gate C — LLM correctness and improvements
1. Deterministic mock baseline first; real provider only with explicit call budget and approved synthetic inputs.
2. Use fixed fixtures including malformed, timeout, snapshot mismatch, completed inspection history, no-evidence cases and critical/normal cases.
3. A/B compare evidence packaging, prompt size, grounded correctness, required-evidence recall, hallucination, stale snapshot rejection, p50/p95 latency, tokens and estimated cost. Hold model/provider/fixtures constant.
4. Require persisted briefing readback and evidence citations, not just HTTP success.
Exit: per-fixture paired results, regression list and cost/latency; no unmeasured claims.

### Gate D — operational recovery / autoscaling
1. Isolated PostgreSQL + separate API and 2/4/8 Worker OS processes; SIGKILL in-flight, lease expiry, fencing, graceful SIGTERM, scale-in.
2. Measure Critical/Normal wait p50/p95, completion, retries, DB load, worker CPU/memory, LLM concurrency and provider quotas.
3. After these pass, provision local Kubernetes (kind/k3d), deploy same image with test-only Secret, test Pod recreation, then KEDA PostgreSQL scaler and 2->4->8->2.
4. No global priority claim, KEDA or cluster verified yet.
Exit: repeatable commands/logs and explicit limits, including local single-host limitations.

## Complexity reduction candidates (not deletions)
P0: in-process API dispatch vs dedicated worker; per-identity static polling; completed-row scan starvation; two independent deployment topologies without shared validation contract.
P1: Outbox worker **exclude from DecisionSession test** but retain until downstream dependency audit; Generator training exclude from online hot path; avoid KEDA until fixed-worker baseline.
P2: Redis only if distributed API rate limit is needed; optional overlays/ingestion paths only if required by fixture; no RabbitMQ/Celery addition.
Protect tenant RLS, idempotency, immutable snapshots, lease/fencing, actual event history, failure truth separation.

## Next implementation slice
- Produce schema/table/field inventory from migrations and actual isolated DB.
- Create sensor quality/replay report from approved fixture files.
- Fix only evidenced blockers, then run deterministic end-to-end and independent worker kill/restart.
- No deployment/LLM spend until those gates pass.
