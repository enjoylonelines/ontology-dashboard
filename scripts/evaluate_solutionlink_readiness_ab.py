#!/usr/bin/env python3
"""Compare an evidence-aware decision gate with an explicit weak baseline.

This is a synthetic contract-regression A/B evaluation.  The baseline is not a
historical deployment: it intentionally models an artifact-presence-only
display rule so that the safety value of the current gate can be measured on
the same frozen scenarios.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # pytest imports `scripts.*`; direct CLI execution puts `scripts/` on sys.path.
    from scripts.evaluate_solutionlink_readiness import _metrics, evaluate
except ModuleNotFoundError:  # pragma: no cover - exercised by the CLI command below.
    from evaluate_solutionlink_readiness import _metrics, evaluate


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_ab(root: Path) -> dict[str, Any]:
    suite_path = root / "evaluation" / "solutionlink_readiness" / "solutionlink-readiness-gold-v1.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    treatment = evaluate(root)
    treatment_by_id = {row["case_id"]: row for row in treatment["rows"]}

    expected_visible = [case["expected"]["action_visible"] for case in suite["cases"]]
    baseline_visible = [bool(case["evidence"].get("artifact_id")) for case in suite["cases"]]
    treatment_visible = [treatment_by_id[case["case_id"]]["action_visible"] for case in suite["cases"]]
    hold_indexes = [index for index, visible in enumerate(expected_visible) if not visible]
    ready_indexes = [index for index, visible in enumerate(expected_visible) if visible]
    expected_broken = [not case["expected"]["lineage_complete"] for case in suite["cases"]]
    treatment_broken = [not treatment_by_id[case["case_id"]]["lineage_complete"] for case in suite["cases"]]

    baseline_unsafe = sum(baseline_visible[index] for index in hold_indexes)
    treatment_unsafe = sum(treatment_visible[index] for index in hold_indexes)
    baseline_valid_visible = sum(baseline_visible[index] for index in ready_indexes)
    treatment_valid_visible = sum(treatment_visible[index] for index in ready_indexes)
    broken_total = sum(expected_broken)
    treatment_detected = sum(want and got for want, got in zip(expected_broken, treatment_broken))

    return {
        "suite_id": suite["suite_id"],
        "schema_version": "solutionlink-readiness-safety-ab-v1",
        "fixture_kind": "synthetic_contract_fixture",
        "comparison": {
            "baseline": {
                "name": "artifact_presence_only_v0",
                "rule": "Show a proposed action when artifact_id is present; do not check freshness, evidence gaps, data-quality hold, asset match, or lifecycle lineage.",
                "historical_deployment_claim": False,
            },
            "treatment": {
                "name": "evidence_aware_gate_v1",
                "rule": "Use the current frozen readiness contract: required evidence, asset match, 24-hour freshness, data-quality hold, evidence gaps, and lifecycle lineage checks.",
            },
        },
        "scenario_count": len(suite["cases"]),
        "decision_visibility": {
            "baseline": _metrics(expected_visible, baseline_visible),
            "treatment": _metrics(expected_visible, treatment_visible),
            "f1_absolute_change": round(
                _metrics(expected_visible, treatment_visible)["f1"]
                - _metrics(expected_visible, baseline_visible)["f1"],
                6,
            ),
        },
        "unsafe_action_exposure": {
            "hold_case_count": len(hold_indexes),
            "baseline_visible_action_count": baseline_unsafe,
            "baseline_rate": _rate(baseline_unsafe, len(hold_indexes)),
            "treatment_visible_action_count": treatment_unsafe,
            "treatment_rate": _rate(treatment_unsafe, len(hold_indexes)),
            "absolute_reduction_percentage_points": round(
                (_rate(baseline_unsafe, len(hold_indexes)) - _rate(treatment_unsafe, len(hold_indexes))) * 100,
                6,
            ),
            "relative_reduction": _rate(baseline_unsafe - treatment_unsafe, baseline_unsafe) if baseline_unsafe else None,
        },
        "valid_action_retention": {
            "ready_case_count": len(ready_indexes),
            "baseline_visible_action_count": baseline_valid_visible,
            "treatment_visible_action_count": treatment_valid_visible,
            "treatment_rate": _rate(treatment_valid_visible, len(ready_indexes)),
        },
        "broken_lineage_detection": {
            "expected_broken_count": broken_total,
            "baseline_detected_count": 0,
            "treatment_detected_count": treatment_detected,
            "absolute_improvement_percentage_points": round(_rate(treatment_detected, broken_total) * 100, 6),
        },
        "claim_boundary": (
            "This is a frozen synthetic counterfactual policy comparison, not a historical production A/B test. "
            "It measures contract-level unsafe action exposure and lineage detection only; it does not measure "
            "LLM accuracy, real outages, factory outcomes, user behavior, latency, or business impact."
        ),
        "pass": treatment["pass"] and baseline_unsafe == 6 and treatment_unsafe == 0 and treatment_detected == broken_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output")
    args = parser.parse_args()
    result = evaluate_ab(Path(args.root))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
