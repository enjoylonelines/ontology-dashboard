#!/usr/bin/env python3
"""Evaluate the SolutionLink evidence/readiness contract against frozen fixtures."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _metrics(expected: list[bool], actual: list[bool]) -> dict[str, Any]:
    true_positive = sum(want and got for want, got in zip(expected, actual))
    false_positive = sum(not want and got for want, got in zip(expected, actual))
    false_negative = sum(want and not got for want, got in zip(expected, actual))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"true_positive": true_positive, "false_positive": false_positive, "false_negative": false_negative, "precision": precision, "recall": recall, "f1": f1}


def evaluate(root: Path) -> dict[str, Any]:
    suite_path = root / "evaluation" / "solutionlink_readiness" / "solutionlink-readiness-gold-v1.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    policy = suite["policy"]
    required = tuple(policy["required_decision_evidence"])
    rows: list[dict[str, Any]] = []

    for case in suite["cases"]:
        evidence = case["evidence"]
        observed_at = _parse_timestamp(evidence.get("observed_at", ""))
        as_of = _parse_timestamp(case["as_of"])
        missing_decision_evidence = [key for key in required if not evidence.get(key)]
        stale = observed_at is None or as_of is None or (as_of - observed_at).total_seconds() > policy["freshness_hours"] * 3600
        blockers: list[str] = []
        if missing_decision_evidence:
            blockers.append("MISSING_DECISION_EVIDENCE")
        if not evidence.get("asset_matches_request", False):
            blockers.append("ASSET_ARTIFACT_MISMATCH")
        if evidence.get("data_quality_hold", False):
            blockers.append("DATA_QUALITY_HOLD")
        if evidence.get("evidence_gaps", []):
            blockers.append("EVIDENCE_GAP")
        if stale:
            blockers.append("FRESHNESS_POLICY_EXCEEDED")
        decision_ready = not blockers

        lifecycle = case["lifecycle"]
        lineage = {**evidence, **case.get("lineage", {})}
        required_lineage = policy["lineage_by_lifecycle"][lifecycle]
        missing_lineage = [key for key in required_lineage if not lineage.get(key)]
        lineage_complete = not missing_lineage
        action_visible = decision_ready
        expected = case["expected"]
        row_pass = (
            decision_ready == expected["decision_ready"]
            and action_visible == expected["action_visible"]
            and lineage_complete == expected["lineage_complete"]
        )
        rows.append({
            "case_id": case["case_id"],
            "decision_ready": decision_ready,
            "action_visible": action_visible,
            "lineage_complete": lineage_complete,
            "blockers": blockers,
            "missing_lineage": missing_lineage,
            "pass": row_pass,
        })

    expected_ready = [case["expected"]["decision_ready"] for case in suite["cases"]]
    actual_ready = [row["decision_ready"] for row in rows]
    expected_lineage = [case["expected"]["lineage_complete"] for case in suite["cases"]]
    actual_lineage = [row["lineage_complete"] for row in rows]
    hold_rows = [row for row in rows if not row["decision_ready"]]
    expected_broken = sum(not value for value in expected_lineage)
    detected_broken = sum(not row["lineage_complete"] for row in rows)
    passed = sum(row["pass"] for row in rows)
    return {
        "suite_id": suite["suite_id"],
        "schema_version": suite["schema_version"],
        "fixture_kind": "synthetic_contract_fixture",
        "policy": policy,
        "scenario_count": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "decision_readiness": _metrics(expected_ready, actual_ready),
        "lineage_completeness": _metrics(expected_lineage, actual_lineage),
        "unsafe_action_exposure": {
            "hold_case_count": len(hold_rows),
            "visible_action_count": sum(row["action_visible"] for row in hold_rows),
            "rate": sum(row["action_visible"] for row in hold_rows) / len(hold_rows) if hold_rows else 0.0,
        },
        "broken_lineage_detection": {"expected_broken": expected_broken, "detected_broken": detected_broken},
        "claim_boundary": "This validates a frozen synthetic contract only. It does not measure LLM accuracy, real factory data quality, maintenance outcomes, cost reduction, or user task performance.",
        "rows": rows,
        "pass": passed == len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output")
    args = parser.parse_args()
    result = evaluate(Path(args.root))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
