# 2026-11-05 — Sensor contract regression and independent Worker restart

## Executed
- `PYTHONPATH=systems/backend:ml/src:tests:. .venv/bin/python -m pytest -q tests/test_predictive_maintenance_bundle_adapter.py tests/test_predictive_maintenance_bundle_contract.py tests/test_canonical_runtime_smoke.py tests/test_decision_session_service.py`
- **29 passed, 2 skipped**, 5 deprecation warnings, 2.02s. Contract/unit tests, not continuous real sensor replay.
- Disposable migrated PostgreSQL 16, 52 migrations; ran `DECISION_LOAD_COUNT=30 DECISION_LOAD_RATE=10 ... python -m tests.personal_decision_independent_worker_load`.
- **30/30 completed, missing 0**; producer 3.013s; all complete 4.431s; restart-to-complete 1.414s; observed E2E p50 1526.0ms / p95 2732.0ms.
- Synthetic agent; no external LLM, API, Kubernetes or real telemetry. One run only.
- Disposable DB stopped and removed; no production DB modified.

## Critical caveat
The existing harness kills the process after producer completion without asserting an active lease at kill time. Thus this demonstrates a restart/completion scenario, **not verified in-flight lease takeover**. E2E timing is polled observation, not pure queue wait.

## Next gates
- Add a synchronized worker fault-injection barrier after lease claim and before completion, prove old owner fencing and recovery after expiry.
- Analyze canonical full-size sensor dataset, timestamp distribution, duplicates, missingness, source lineage and outliers; adapter fixture files alone are too small.
- Run actual sensor-to-prediction-to-event-to-saved-briefing deterministic E2E.
- Keep real LLM A/B on fixed evidence with approved cost budget.

Human hypothesis/prediction and adoption decision: unrecorded.
