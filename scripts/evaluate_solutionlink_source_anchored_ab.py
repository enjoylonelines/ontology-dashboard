#!/usr/bin/env python3
"""A source-anchored synthetic safety A/B for SolutionLink readiness.

Seeds are selected from a versioned Canonical timeline.  Each declared mutation
creates a controlled incomplete-evidence condition.  This improves provenance
and sample selection transparency over a hand-authored-only fixture, but it is
still not independent labeling or an operational production A/B experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


MUTATIONS = (
    ("current_complete", True, True),
    ("evidence_gap", False, True),
    ("data_quality_hold", False, True),
    ("stale_observation", False, True),
    ("asset_artifact_mismatch", False, True),
    ("missing_artifact_id", False, True),
    ("approved_lineage_missing", True, False),
)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics(expected: list[bool], actual: list[bool]) -> dict[str, float | int]:
    tp = sum(want and got for want, got in zip(expected, actual))
    fp = sum(not want and got for want, got in zip(expected, actual))
    fn = sum(want and not got for want, got in zip(expected, actual))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def _case(seed: dict[str, Any], mutation: str, freshness_hours: int) -> dict[str, Any]:
    observed_at = _timestamp(seed["observed_at"])
    evidence = {
        "asset_id": seed["asset_id"],
        "artifact_id": f"RESULT#{seed['prediction_id']}",
        "observed_at": seed["observed_at"],
        "canonical_snapshot_id": f"SNAP#{seed['prediction_id']}",
        "evidence_package_id": f"EVIDENCE#{seed['prediction_id']}",
        "asset_matches_request": True,
        "data_quality_hold": False,
        "evidence_gaps": [],
    }
    as_of = observed_at + timedelta(hours=1)
    lifecycle = "none"
    lineage: dict[str, str] = {}
    if mutation == "evidence_gap":
        evidence["evidence_gaps"] = ["maintenance_context"]
    elif mutation == "data_quality_hold":
        evidence["data_quality_hold"] = True
    elif mutation == "stale_observation":
        as_of = observed_at + timedelta(hours=freshness_hours, seconds=1)
    elif mutation == "asset_artifact_mismatch":
        evidence["asset_matches_request"] = False
    elif mutation == "missing_artifact_id":
        evidence["artifact_id"] = ""
    elif mutation == "approved_lineage_missing":
        lifecycle = "approved"
        lineage = {"work_order_id": f"WO#{seed['asset_id']}", "assignment_activity_id": "ASSIGN-1", "assignee_id": "ANON-1", "approval_activity_id": ""}
    return {"seed_prediction_id": seed["prediction_id"], "asset_type": seed["asset_type"], "mutation": mutation, "evidence": evidence, "as_of": as_of.isoformat(), "lifecycle": lifecycle, "lineage": lineage}


def _treatment(case: dict[str, Any], freshness_hours: int) -> tuple[bool, bool]:
    evidence = case["evidence"]
    observed_at = _timestamp(evidence["observed_at"])
    as_of = _timestamp(case["as_of"])
    ready = bool(evidence["artifact_id"]) and bool(evidence["canonical_snapshot_id"]) and bool(evidence["evidence_package_id"])
    ready = ready and bool(evidence["asset_matches_request"]) and not bool(evidence["data_quality_hold"]) and not evidence["evidence_gaps"]
    ready = ready and (as_of - observed_at).total_seconds() <= freshness_hours * 3600
    lineage_complete = case["lifecycle"] != "approved" or bool(case["lineage"].get("approval_activity_id"))
    return ready, lineage_complete


def evaluate(root: Path, source_timeline: Path | None = None) -> dict[str, Any]:
    suite = json.loads((root / "evaluation/solutionlink_readiness/source-anchored-heldout-v1.json").read_text(encoding="utf-8"))
    source_verification: dict[str, Any] = {"checked": False}
    if source_timeline:
        actual_hash = _sha256(source_timeline)
        source_rows = {json.loads(line)["prediction_id"] for line in source_timeline.read_text(encoding="utf-8").splitlines() if line.strip()}
        source_verification = {"checked": True, "sha256_matches": actual_hash == suite["source"]["timeline_sha256"], "all_seed_predictions_present": all(seed["prediction_id"] in source_rows for seed in suite["seeds"])}

    cases = [_case(seed, mutation, suite["policy"]["freshness_hours"]) for seed in suite["seeds"] for mutation, _, _ in MUTATIONS]
    expected_visible = [next(visible for name, visible, _ in MUTATIONS if name == case["mutation"]) for case in cases]
    expected_lineage = [next(lineage for name, _, lineage in MUTATIONS if name == case["mutation"]) for case in cases]
    baseline_visible = [bool(case["evidence"]["artifact_id"]) for case in cases]
    treatment = [_treatment(case, suite["policy"]["freshness_hours"]) for case in cases]
    treatment_visible = [result[0] for result in treatment]
    treatment_lineage = [result[1] for result in treatment]
    hold_indexes = [index for index, expected in enumerate(expected_visible) if not expected]
    ready_indexes = [index for index, expected in enumerate(expected_visible) if expected]
    broken_indexes = [index for index, expected in enumerate(expected_lineage) if not expected]
    baseline_unsafe = sum(baseline_visible[index] for index in hold_indexes)
    treatment_unsafe = sum(treatment_visible[index] for index in hold_indexes)
    detected_broken = sum(not treatment_lineage[index] for index in broken_indexes)
    result = {
        "suite_id": suite["suite_id"], "schema_version": "solutionlink-source-anchored-safety-ab-result-v1", "fixture_kind": "source_anchored_synthetic_mutation_suite",
        "source_verification": source_verification,
        "sample": {"seed_count": len(suite["seeds"]), "scenario_count": len(cases), "asset_type_counts": {kind: sum(seed["asset_type"] == kind for seed in suite["seeds"]) for kind in ("compressor", "cnc")}},
        "decision_visibility": {"baseline": _metrics(expected_visible, baseline_visible), "treatment": _metrics(expected_visible, treatment_visible)},
        "unsafe_action_exposure": {"hold_case_count": len(hold_indexes), "baseline_visible_action_count": baseline_unsafe, "baseline_rate": baseline_unsafe / len(hold_indexes), "treatment_visible_action_count": treatment_unsafe, "treatment_rate": treatment_unsafe / len(hold_indexes), "absolute_reduction_percentage_points": round((baseline_unsafe - treatment_unsafe) / len(hold_indexes) * 100, 6)},
        "valid_action_retention": {"ready_case_count": len(ready_indexes), "baseline_visible_action_count": sum(baseline_visible[index] for index in ready_indexes), "treatment_visible_action_count": sum(treatment_visible[index] for index in ready_indexes)},
        "broken_lineage_detection": {"expected_broken_count": len(broken_indexes), "baseline_detected_count": 0, "treatment_detected_count": detected_broken},
        "claim_boundary": "Source rows are deterministically selected from a versioned local synthetic Canonical replay, but incompleteness labels are declared mutations and self-labeled. This is not independent human labeling, a production A/B, real-outage sampling, LLM quality evidence, or user/business outcome evidence.",
    }
    result["pass"] = (not source_verification.get("checked") or all(source_verification.values())) and result["decision_visibility"]["treatment"]["f1"] == 1.0 and treatment_unsafe == 0 and detected_broken == len(broken_indexes)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--source-timeline", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(Path(args.root), args.source_timeline)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
