from __future__ import annotations

from pathlib import Path

from scripts.evaluate_solutionlink_source_anchored_ab import evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_source_anchored_evidence_gate_blocks_declared_incomplete_cases() -> None:
    result = evaluate(ROOT)

    assert result["pass"] is True
    assert result["sample"] == {"seed_count": 12, "scenario_count": 84, "asset_type_counts": {"compressor": 6, "cnc": 6}}
    assert result["decision_visibility"]["baseline"]["f1"] == 0.5
    assert result["decision_visibility"]["treatment"]["f1"] == 1.0
    assert result["unsafe_action_exposure"] == {"hold_case_count": 60, "baseline_visible_action_count": 48, "baseline_rate": 0.8, "treatment_visible_action_count": 0, "treatment_rate": 0.0, "absolute_reduction_percentage_points": 80.0}
    assert result["valid_action_retention"] == {"ready_case_count": 24, "baseline_visible_action_count": 24, "treatment_visible_action_count": 24}
    assert result["broken_lineage_detection"] == {"expected_broken_count": 12, "baseline_detected_count": 0, "treatment_detected_count": 12}
