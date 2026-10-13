from scripts.evaluate_solutionlink_priority_replay import average_precision, rank_metrics, roc_auc


def test_priority_ranking_reports_capture_over_same_time_candidate_sets() -> None:
    rows = [
        {"observed_at": "2026-08-01T00:00:00+09:00", "asset_id": "A", "failure_probability": 0.9, "label": 1},
        {"observed_at": "2026-08-01T00:00:00+09:00", "asset_id": "B", "failure_probability": 0.5, "label": 0},
        {"observed_at": "2026-08-01T01:00:00+09:00", "asset_id": "A", "failure_probability": 0.2, "label": 0},
        {"observed_at": "2026-08-01T01:00:00+09:00", "asset_id": "B", "failure_probability": 0.8, "label": 1},
    ]

    ranking = rank_metrics(rows, [1])

    assert ranking["candidate_windows"] == 2
    assert ranking["positive_windows"] == 2
    assert ranking["top_k"]["1"] == {
        "selected_asset_windows": 2,
        "true_positive_asset_windows": 2,
        "precision": 1.0,
        "recall": 1.0,
    }
    assert average_precision(rows) == 1.0
    assert roc_auc(rows) == 1.0
