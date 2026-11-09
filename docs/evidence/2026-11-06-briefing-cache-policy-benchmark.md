# 2026-11-06 — Snapshot-safe GET fix and policy baseline comparison

## Code change
- Removed `LATEST_STORED` fallback from `ManufacturingPredictiveMaintenanceService.cached_agent_review_summary_for_packet` in `systems/backend/app/operations/service.py`.
- Exact snapshot miss now returns pending instead of stale prose; no LLM invocation from GET.
- Updated old fallback-expecting test in `tests/test_operations.py` to require `INELIGIBLE` and changed pending materialization key.
- Regressions: `APP_ENV=test ONTOLOGY_DASHBOARD_ALLOW_HEURISTIC_MODEL_FALLBACK=1 PYTHONPATH=systems/backend:ml/src:tests:. .venv/bin/python -m pytest -q tests/test_agent_prediction_to_screen_chain.py tests/test_agent_briefing_demand_efficiency.py tests/test_agent_review_generation_policy.py tests/test_agent_review_material_change.py`: **62 passed**, 5 deprecation warnings, 19.70s. Focused suite including changed operations test: **24 passed**.
- Broad test suite including all of `tests/test_operations.py` exceeded 110s timeout; do not claim full-suite pass.
- `git diff --check` clean.

## Matched-fixture simulation, NOT live provider measurement
Command: `APP_ENV=test ONTOLOGY_DASHBOARD_ALLOW_HEURISTIC_MODEL_FALLBACK=1 PYTHONPATH=systems/backend:ml/src:tests:. .venv/bin/python -c 'from scripts.evaluate_agent_review_generation_policy import evaluate; ...'`
Existing deterministic `scripts/evaluate_agent_review_generation_policy.py`, 8 scenarios × 10 snapshots = 80 snapshots; 240 simulated GET queries.

| Metric | always | hybrid |
|---|---:|---:|
| Watcher background generation starts | 57 | 51 |
| Explicit refresh generation starts | 5 | 5 |
| Total generation starts | 62 | 56 |
| Simulated retries | 9 | 9 |
| Critical generation requests | 40/40 | 40/40 |
| Exact current-summary query hits | 141/240 | 112/240 |

- Background starts decrease 6/57 = **10.53%**; total starts decrease 6/62 = **9.68%**.
- Simulated latest-query availability drops from 58.75% to 46.67% (12.08 percentage points); optimization is a trade-off, not unqualified improvement.
- No real LLM provider invoked; provider call count, input/output tokens, actual spend and latency **not measured**. Do not convert generation starts into actual calls or claim token savings. No tiktoken installed in environment.
- Existing simulation models scheduling and completion assumptions, not durable queue execution or production watcher.
- Default policy may be `always` unless configured `hybrid`; this change does not globally switch deployment policy or implement a new persistent watcher queue.

## Follow-up
- Instrument actual provider `usage` per successful and failed attempt; paired replay of identical snapshot stream under `always` and `hybrid`, with request IDs, retry/repair, token and cost attribution.
- Verify watcher initial-coverage, durable reservation/retry/backoff and crash recovery separately.
- Decide acceptable latest-summary availability before choosing deployment policy.
