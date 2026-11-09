# 2026-11-05 — Isolated PostgreSQL schema and queue validation

## Environment
- Disposable Docker container `ontology-validation-pg`, pgvector/pgvector:pg16, loopback port 55439, isolated database `ontology`.
- Project migration function applied 52 migrations successfully.
- 145 public tables observed, including partitions; not a count of logical entities.
- Verified RLS policies exist for `decision_agent_runs`, `pm_compressor_observations`, `pm_cnc_observations`, `pm_runtime_overlay_observations`.
- `decision_agent_runs` indexes: primary key and `idx_decision_agent_runs_scope`; no explicit priority/queue-ready partial index observed.

## Executed
`DECISION_TEST_POSTGRES_DSN=postgresql://<isolated-local-credentials>@127.0.0.1:55439/ontology PYTHONPATH=systems/backend:ml/src:tests:. .venv/bin/python -m pytest -q tests/test_personal_decision_postgresql_queue.py`

Result: **2 passed in 4.21s** (concurrent duplicate request and 100 undispatched resumes).
The container was stopped and removed afterwards. No production DB touched.

## Schema / data findings
- `decision_agent_runs` is scoped by organization/project/identity_hash and persists JSON text plus binding and lease owner/expiry. The pending query limits rows before checking JSON result completion, so pending work can be hidden by earlier completed rows. Priority classes are not in this schema.
- Canonical compressor/CNC observations use typed timestamped partitioned tables, primary key `(dataset_version_id,asset_id,observed_at)`, and FK to `pm_assets`.
- Runtime overlay is a separate source with JSONB observation and source kind; should not be silently mixed with canonical observations.
- Fixture adapter CSVs: Azure maintenance 4 rows, MetroPT compressor 3 rows. These are tiny mapping fixtures, not representative operational workloads.
- RLS **policy presence** was inspected; adversarial cross-tenant behavior was not tested in this run.

## Not validated
- End-to-end sensor ingestion, model inference, event generation, saved briefing readback.
- Data quality over full canonical sensor corpus.
- In-flight SIGKILL, fencing race, queue wait p95, Kubernetes/KEDA, real LLM A/B.

## Follow-up / decision gate
1. Reproduce pending-row starvation with >50 completed runs and one pending run, then fix query with SQL-side result filtering/index and regression test.
2. Inspect sensor provenance, duplicates, missing timestamps and 10-minute sampling contract on representative data.
3. Run deterministic E2E with separate API and Worker, then fault injection.
4. Compare LLM baseline/challenger on fixed evidence after lineage issues are addressed.
Human hypothesis and changed belief: unrecorded. Human adoption decision: pending.
