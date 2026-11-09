# 2026-11-06 — Stale briefing read-path root cause

## Reproduction
`PYTHONPATH=systems/backend:ml/src:tests:. .venv/bin/python -m pytest -xq tests/test_agent_prediction_to_screen_chain.py::test_changed_prediction_input_invalidates_stored_prose --tb=short`

Expected HTTP 202 after mutation; actual HTTP 200 with prior materialization.

## Instrumented before/after
- Sensor torque: 55.0 -> 67.0.
- Observation: 2026-08-01T00:00:00+09:00 -> 2026-08-01T00:10:00+09:00.
- Packet snapshot artifact ID changed accordingly.
- Independently computed new summary key: `agent-review-summary:0958504ab7e7e36173c71478e5f6fc677ca505655595447a8f44099775fe1b25`.
- Original key: `agent-review-summary:19ecfd255b03543df7a72ff386e4f9e6961d41646153fff51ec39bb44601a1cf`.
- Actual API and direct service read returned old materialization key and old `decision_as_of`; `reused=true`.

## Confirmed code-level root cause
In `systems/backend/app/operations/service.py`, `cached_agent_review_summary_for_packet` first performs exact validated lookup through `SnapshotGuardedRepository`. On lookup miss, it then calls `self.repository.latest_agent_review_summary(...)` and assigns `summary = latest['summary']`, `reuse_eligibility = 'LATEST_STORED'`. This **bypasses current snapshot eligibility** and exposes stale prose as current, even though fingerprint calculation correctly changed.

## Proposed fix, not applied
Remove the `LATEST_STORED` fallback from the current-summary serving path; return 202 with pending trace on exact-key miss. If history is desired, expose it through a separate explicitly stale/history interface. Add a regression asserting changed snapshot -> 202, then generation -> 200, unchanged snapshot -> no new LLM invocation.

Temporary diagnostic changes to the failing test were reverted after measurement. No production DB or real LLM calls.
