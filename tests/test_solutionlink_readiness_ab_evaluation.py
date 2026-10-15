from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evaluate_solutionlink_readiness_ab import evaluate_ab


ROOT = Path(__file__).resolve().parents[1]


def test_evidence_aware_gate_removes_seeded_unsafe_action_exposure() -> None:
    result = evaluate_ab(ROOT)

    assert result["pass"] is True
    assert result["decision_visibility"]["baseline"]["f1"] == pytest.approx(0.75)
    assert result["decision_visibility"]["treatment"]["f1"] == 1.0
    assert result["unsafe_action_exposure"] == {
        "hold_case_count": 7,
        "baseline_visible_action_count": 6,
        "baseline_rate": 6 / 7,
        "treatment_visible_action_count": 0,
        "treatment_rate": 0.0,
        "absolute_reduction_percentage_points": 85.714286,
        "relative_reduction": 1.0,
    }
    assert result["valid_action_retention"] == {
        "ready_case_count": 9,
        "baseline_visible_action_count": 9,
        "treatment_visible_action_count": 9,
        "treatment_rate": 1.0,
    }
    assert result["broken_lineage_detection"] == {
        "expected_broken_count": 6,
        "baseline_detected_count": 0,
        "treatment_detected_count": 6,
        "absolute_improvement_percentage_points": 100.0,
    }
    assert "not a historical production A/B test" in result["claim_boundary"]
