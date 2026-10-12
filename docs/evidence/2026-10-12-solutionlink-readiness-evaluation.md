# SolutionLink readiness contract evaluation — 2026-10-12

## Purpose

This is a reproducible **synthetic contract** evaluation for the SolutionLink
Decision Workspace. It tests three safety properties that can be checked before
a human study or production-data evaluation:

1. Is a decision shown only when its asset, artifact, snapshot, evidence package,
   freshness, quality, and gap state permit it?
2. Does every hold state keep a proposed action hidden?
3. When the UI claims a maintenance lifecycle state, are the required work-order
   and activity links present?

The policy deliberately mirrors the current Operations freshness policy:
`observed_at` must be no older than 24 hours at the decision `as_of` time. This
is a product policy, not a domain invariant.

## Reproduce

```bash
python3 scripts/evaluate_solutionlink_readiness.py --root . \
  --output evaluation/results/solutionlink-readiness-gold-v1.json
pytest -q tests/test_solutionlink_readiness_evaluation.py
```

The frozen input is
`evaluation/solutionlink_readiness/solutionlink-readiness-gold-v1.json`. It has
16 deliberately small cases: fresh complete evidence, evidence gap, quality
hold, stale observation, asset mismatch, missing trace identifiers, and
assigned/approved/completed lifecycle links.

## Measured outputs

| Measure | Meaning | Result scope |
| --- | --- | --- |
| Decision-readiness precision / recall / F1 | Agreement with frozen `ready`/`hold` labels | Contract-regression only |
| Unsafe action exposure | A proposed action visible in an expected hold case | Contract-regression only |
| Lineage completeness precision / recall / F1 | Agreement that required lifecycle links are present | Contract-regression only |
| Broken-lineage detection | Missing required links detected among seeded broken cases | Contract-regression only |

The generated result is tracked only because the input, policy, command, and
claim boundary are all versioned together.

## Explicit limits

- The labels and data are synthetic; they do not estimate real source outage
  rates, model accuracy, or factory data quality.
- This is not an LLM evaluation. It does not measure answer quality,
  hallucination, latency, or cost.
- It does not validate work-order API writes, a real maintenance outcome, cost
  reduction, downtime prevention, or RPN change.
- It does not establish that a person understands the UI or completes a task
  faster.

## Next stronger evidence

After a reviewable sample exists, create a held-out set of 30–50 cases from
versioned source snapshots. Label only the three fields above (`ready/hold`,
action visibility, required trace links), freeze adjudication notes, and report
the same metrics by failure type. A separate 3–5 participant, within-subject
task test can then measure source-confirmation time and decision errors; it
must not be merged with this engineering acceptance result.
