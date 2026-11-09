# 2026-11-06 — Paired briefing policy payload A/B

## Scope
- Baseline: `always`; challenger: `hybrid`.
- Same fixed fixture: 8 scenarios × 10 snapshots = 80, 240 simulated GET queries.
- Same synthetic completion/failure/retry profile, no real external LLM calls.
- Prompt UTF-8 bytes computed from actual system prompt and `build_tool_selected_agent_review_summary_prompt_payload` per simulated generation start.
- This is a scheduling and prompt-size **proxy**, not token/cost measurement.

## Reproduction
```sh
APP_ENV=test ONTOLOGY_DASHBOARD_ALLOW_HEURISTIC_MODEL_FALLBACK=1 \
PYTHONPATH=systems/backend:ml/src:tests:. \
.venv/bin/python scripts/benchmark_briefing_policy_payload.py \
  --output docs/evidence/2026-11-06-briefing-policy-payload-benchmark.json
```

## Result
| Metric | Always | Hybrid |
|---|---:|---:|
| Simulated generation starts | 62 | 56 |
| Simulated prompt input UTF-8 bytes | 2,345,320 | 2,110,074 |
| Injected retries | 9 | 9 |
| Critical scheduling coverage | 40/40 | 40/40 |
| Exact current-query hits | 141/240 | 112/240 |

- Generation starts: -6 / 62 = **-9.68%**.
- Simulated prompt bytes: -235,246 / 2,345,320 = **-10.03%**.
- Latest exact-read availability: **58.75% -> 46.67%**; trade-off remains unresolved.
- Provider-reported prompt/completion tokens, billable provider calls, real costs: **not measured** (no provider credentials in active process).
- Actual tokenizer-specific counts cannot be inferred reliably from bytes.
- Provider adapter already exposes `usage` when returned by provider, including repair attempts. A real paired run needs credentials and spend authorization, then record actual usage and quality/safety acceptance.

## Verification
```sh
APP_ENV=test ONTOLOGY_DASHBOARD_ALLOW_HEURISTIC_MODEL_FALLBACK=1 \
PYTHONPATH=systems/backend:ml/src:tests:. \
.venv/bin/python -m pytest -q \
  tests/test_briefing_policy_payload_benchmark.py \
  tests/test_agent_briefing_demand_efficiency.py \
  tests/test_agent_review_generation_policy.py \
  tests/test_agent_review_material_change.py \
  tests/test_agent_prediction_to_screen_chain.py
```
**63 passed**, 5 deprecation warnings, 27.22s. `git diff --check` clean.

## Decision
Human hypothesis / predicted savings / adoption decision: unrecorded.
Recommendation: do not claim production token savings or deploy hybrid solely on reduced generation starts; evaluate exact-read availability gate and live provider usage first.
