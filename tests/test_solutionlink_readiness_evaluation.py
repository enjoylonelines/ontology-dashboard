from __future__ import annotations

from pathlib import Path

from scripts.evaluate_solutionlink_readiness import evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_solutionlink_readiness_gold_contract_blocks_unsafe_actions() -> None:
    result = evaluate(ROOT)

    assert result["scenario_count"] == 16
    assert result["passed"] == 16
    assert result["decision_readiness"]["f1"] == 1.0
    assert result["lineage_completeness"]["f1"] == 1.0
    assert result["unsafe_action_exposure"] == {
        "hold_case_count": 7,
        "visible_action_count": 0,
        "rate": 0.0,
    }
    assert result["broken_lineage_detection"] == {"expected_broken": 6, "detected_broken": 6}
    assert "does not measure LLM accuracy" in result["claim_boundary"]
