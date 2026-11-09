# 2026-11-05 — Decision queue pending-scan fix

## Observed defect
`DecisionRunRepository.list_pending` previously applied `LIMIT 50` before Python filtered completed `state_json.result`. Completed rows could conceal a later pending run.

## Minimal change
- `systems/backend/app/infra/db/decision_run_repository.py`: apply completion filter in SQL before ORDER BY/LIMIT; PostgreSQL uses `state_json::jsonb -> 'result'`, SQLite uses `json_extract`. Python retains defensive completion check.
- `tests/test_personal_decision_postgresql_queue.py`: regression inserts 55 completed rows and 1 pending row in the same identity scope, verifies pending discovery at limit 50.

## Executed evidence
- Disposable local `pgvector/pgvector:pg16` on 127.0.0.1:55439; 52 migrations applied.
- PostgreSQL integration: **3 passed in 4.49s**.
- Pressure/recovery regression: **8 passed in 25.28s**.
- `git diff --check` passed. Container stopped and removed.
- No real LLM calls, no production DB, no Kubernetes cluster.

## Limitations
- PostgreSQL JSON cast may be expensive without an appropriate partial/expression index at scale; query plan and throughput not yet measured.
- No global priority scheduling, no tenant-wide work discovery, no true in-flight SIGKILL recovery verified by this test.
- Existing user changes preserved. No commit/push.

Human hypothesis/prediction: unrecorded. Adoption/changed belief: pending human decision.
