# 2026-11-05 — Three-track validation, partial results and blocker

## Track 1: lease takeover and stale-owner fencing
- Added `test_postgresql_expired_lease_reclaimed_and_stale_owner_fenced` to `tests/test_personal_decision_postgresql_queue.py`.
- In disposable migrated PostgreSQL (52 migrations), first owner claimed 0.3s lease; second owner initially received Busy; after 0.5s expiry second owner claimed; first owner's save and heartbeat raised LeaseLost; replacement's result persisted.
- **4 PostgreSQL tests passed in 4.45s**. This proves DB-level lease takeover/fencing, NOT synchronized real in-flight OS SIGKILL.
- Disposable container stopped and removed.

## Track 2: sensor contract and data quality
- Executed bundle adapter and bundle contract tests with E2E suite; included checks for unknown observation asset, duplicate timeline identity, checksum and truth isolation.
- Full-size raw sensor corpus not available under `data/` (only two tiny adapter CSV files located); no representative 100/500/1000-asset time-series audit or actual live ingest was performed.
- No synthetic large-volume metrics are represented as real data.

## Track 3: prediction-to-screen and briefing
- Executed `tests/test_agent_prediction_to_screen_chain.py`, `tests/test_final_briefing_demo_replay.py`, bundle adapter and contract suites.
- **42 passed, 1 failed, 2 skipped** in 5.43s.
- Failing case: `test_changed_prediction_input_invalidates_stored_prose`; after mutation of sensor torque and timestamp, GET /api/objects/{asset}/agent-review-summary returned 200 instead of expected 202. Do not claim snapshot invalidation works.
- Existing integration harness uses a controlled LLM transport (not real external provider), real FastAPI TestClient, persistence and read API. No real LLM A/B conducted.
- Next investigation: compare original vs mutated packet snapshot basis and summary_key, identify whether event selection or fixture-to-view-model invalidation is stale; do not weaken assertion to pass.

## Scope and next gate
- No commit/push; production DB untouched; no actual LLM spend.
- Next: instrument failing E2E snapshot fingerprints; repair proven stale path, rerun. Add synchronized process SIGKILL after claim, then sample real canonical source with provenance and data-quality statistics.
- Human hypothesis, prediction, adoption decision: unrecorded.
