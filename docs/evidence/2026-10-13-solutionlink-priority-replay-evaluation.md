# SolutionLink inspection-priority replay evaluation — 2026-10-13

## Question

At a given decision time, does the risk ranking place equipment with a
failure in the next 24 hours near the top of the inspection queue?

## Method

- Source: local Canonical V3.1 synthetic package, not the runtime database.
- Truth: the package's separate `canonical/evaluation_truth/*_failure_truth.csv`.
  Runtime/API/dashboard/LLM paths remain forbidden from reading this directory.
- Scores: `prediction_timeline.jsonl` (68,208 hourly rows) whose contract states
  every site is scored by a model trained on the other sites (leave-one-site-out).
- Label: an asset is positive only when a failure occurs strictly after the
  observation and within the stated 24-hour horizon.
- Candidate set: all available timeline rows at the same `observed_at`; ties are
  resolved by `asset_id` only to make Top-K replay deterministic.
- Integrity: every listed evaluation-truth and model-output checksum in
  `model_contract.json` must match before metrics can pass.

Run from the repository root:

```bash
python3 scripts/evaluate_solutionlink_priority_replay.py \
  --package-root /path/to/predictive_maintenance_canonical_v3.1 \
  --output evaluation/results/solutionlink-canonical-priority-replay-v1.json
```

## Fixed replay result

| Measure | Result |
| --- | ---: |
| Package checksum contract | 14 / 14 matching |
| Candidate decision windows | 690 |
| Positive asset-windows | 1,792 |
| Top-5 precision | 26.61% |
| Top-5 recall | 51.23% |
| Top-10 precision | 15.68% |
| Top-10 recall | 60.38% |
| CNC LOSO ROC-AUC / AP | 0.813 / 0.530 |
| Compressor LOSO ROC-AUC / AP | 0.734 / 0.222 |

`Top-5 recall` means that, among the 1,792 synthetic asset-time windows with
a known next-24-hour failure, 918 were in the five highest-scored available
assets for that same time. It does **not** mean 51.23% of real faults are
prevented or that five tasks should be automatically created.

## Claim boundary

This is a reproducible, offline result over a local synthetic Canonical V3.1
package. It demonstrates a site-held-out score/ranking contract and its
priority replay calculation. It does not establish live-factory accuracy,
maintenance savings, downtime reduction, user adoption, or an automatic-action
policy. A human still checks freshness, production impact, and missing evidence
before initiating work.
