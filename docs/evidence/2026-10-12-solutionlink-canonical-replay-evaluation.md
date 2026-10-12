# SolutionLink Canonical V3.1 replay cohort — 2026-10-12

## What this evaluates

The prior 16-case readiness suite checks synthetic edge contracts. This second
evaluation reads a deterministic 40-artifact cohort from the locally loaded
Canonical V3.1 replay database, without issuing any write.

It checks:

1. every result has its artifact, prediction, result, asset, observation time,
   and source hash reference;
2. stored provenance identifies the fixed dataset/version and says its Canonical
   source was not mutated;
3. the same cohort is fresh at its historical `as_of` time, but stale at the
   fixed current `as_of` time under the 24-hour Operations policy;
4. schema version, model version, and source hash do not silently drift inside
   the cohort.

## Reproduce

```bash
python3 scripts/evaluate_solutionlink_canonical_replay.py --root . \
  --database-url "$ONTOLOGY_DASHBOARD_DATABASE_URL" \
  --output evaluation/results/solutionlink-canonical-replay-cohort-v1.json
```

The database URL is intentionally required as an argument: the evaluator does
not choose a shared or production database. The evaluated local dataset ID and
deterministic `artifact_id ASC / LIMIT 40` selection are frozen in
`evaluation/solutionlink_readiness/canonical-v31-replay-cohort-v1.json`. Its
ordered identity/value fingerprint is also frozen, so a changed cohort fails
instead of silently becoming a new baseline.

## Boundary

Canonical V3.1 is a local synthetic replay. Therefore this produces evidence of
stored snapshot integrity and stale-view containment only. It does not measure
an unseen ML test set, current factory conditions, API write safety, LLM quality,
or business outcomes.
