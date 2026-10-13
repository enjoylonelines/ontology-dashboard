#!/usr/bin/env python3
"""Evaluate Canonical V3.1 inspection-priority ranking outside runtime surfaces.

This program deliberately reads the package's separate ``evaluation_truth``
directory.  That directory must never be added to the dashboard, API, or LLM
input path; this is an offline, reproducible evaluation only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_truth(paths: list[Path]) -> dict[str, list[datetime]]:
    events: dict[str, list[datetime]] = defaultdict(list)
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                events[str(row["asset_id"])].append(timestamp(row["failure_occurred_at"]))
    return {asset_id: sorted(values) for asset_id, values in events.items()}


def has_failure_within_horizon(
    observed_at: datetime,
    events: list[datetime],
    horizon_hours: int,
) -> bool:
    end_at = observed_at + timedelta(hours=horizon_hours)
    return any(observed_at < event_at <= end_at for event_at in events)


def average_precision(rows: list[dict[str, Any]]) -> float:
    positive_count = sum(row["label"] for row in rows)
    if not positive_count:
        return 0.0
    ordered = sorted(rows, key=lambda row: float(row["failure_probability"]), reverse=True)
    total_seen = 0
    positives_seen = 0
    score = 0.0
    index = 0
    while index < len(ordered):
        probability = float(ordered[index]["failure_probability"])
        end = index
        while end < len(ordered) and float(ordered[end]["failure_probability"]) == probability:
            end += 1
        group = ordered[index:end]
        total_seen += len(group)
        positives_seen += sum(row["label"] for row in group)
        score += (positives_seen / total_seen) * (sum(row["label"] for row in group) / positive_count)
        index = end
    return score


def roc_auc(rows: list[dict[str, Any]]) -> float:
    positives = sum(row["label"] for row in rows)
    negatives = len(rows) - positives
    if not positives or not negatives:
        return 0.0
    ordered = sorted(rows, key=lambda row: float(row["failure_probability"]))
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        probability = float(ordered[index]["failure_probability"])
        end = index
        while end < len(ordered) and float(ordered[end]["failure_probability"]) == probability:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(row["label"] for row in ordered[index:end])
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def rank_metrics(rows: list[dict[str, Any]], top_k_values: list[int]) -> dict[str, Any]:
    by_timestamp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_timestamp[str(row["observed_at"])].append(row)
    positive_rows = [row for row in rows if row["label"]]
    result: dict[str, Any] = {
        "candidate_windows": len(by_timestamp),
        "positive_windows": sum(any(row["label"] for row in window) for window in by_timestamp.values()),
        "positive_asset_windows": len(positive_rows),
        "top_k": {},
    }
    for top_k in top_k_values:
        selected = [
            row
            for window in by_timestamp.values()
            for row in sorted(
                window,
                key=lambda item: (-float(item["failure_probability"]), str(item["asset_id"])),
            )[:top_k]
        ]
        selected_positives = sum(row["label"] for row in selected)
        result["top_k"][str(top_k)] = {
            "selected_asset_windows": len(selected),
            "true_positive_asset_windows": selected_positives,
            "precision": selected_positives / len(selected) if selected else 0.0,
            "recall": selected_positives / len(positive_rows) if positive_rows else 0.0,
        }
    return result


def _check_hashes(package_root: Path, contract: dict[str, Any]) -> dict[str, bool]:
    canonical = package_root / "canonical"
    checks: dict[str, bool] = {}
    for filename, expected in (contract.get("canonical_input_sha256") or {}).items():
        checks[f"dataset/{filename}"] = sha256(canonical / "dataset" / filename) == expected
    for filename, expected in (contract.get("evaluation_truth_input_sha256") or {}).items():
        checks[f"evaluation_truth/{filename}"] = sha256(canonical / "evaluation_truth" / filename) == expected
    for filename, expected in (contract.get("output_sha256") or {}).items():
        checks[f"model_outputs/{filename}"] = sha256(canonical / "model_outputs" / filename) == expected
    return checks


def evaluate(package_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    canonical = package_root / "canonical"
    contract = json.loads((canonical / "model_outputs" / "model_contract.json").read_text(encoding="utf-8"))
    timeline = read_jsonl(canonical / "model_outputs" / "prediction_timeline.jsonl")
    horizon_hours = int(config["horizon_hours"])
    truth = load_truth(
        [
            canonical / "evaluation_truth" / "compressor_failure_truth.csv",
            canonical / "evaluation_truth" / "cnc_failure_truth.csv",
        ]
    )
    labelled_rows = []
    for row in timeline:
        if int(row["prediction_horizon_hours"]) != horizon_hours:
            raise ValueError(f"prediction horizon mismatch for {row['prediction_id']}")
        if row["model_version"] != config["model_version"]:
            raise ValueError(f"model version mismatch for {row['prediction_id']}")
        labelled_rows.append(
            {
                **row,
                "label": int(
                    has_failure_within_horizon(
                        timestamp(row["observed_at"]),
                        truth.get(str(row["asset_id"]), []),
                        horizon_hours,
                    )
                ),
            }
        )
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in labelled_rows:
        by_type[str(row["asset_type"])].append(row)
    model_metrics = {
        asset_type: {
            "rows": len(rows),
            "positive_rows": sum(row["label"] for row in rows),
            "roc_auc": roc_auc(rows),
            "average_precision": average_precision(rows),
        }
        for asset_type, rows in sorted(by_type.items())
    }
    checks = _check_hashes(package_root, contract)
    expected = config["expected"]
    result = {
        "suite_id": config["schema_version"],
        "fixture_kind": config["source_kind"],
        "dataset_version": contract["dataset_version"],
        "model_version": contract["model_version"],
        "timeline_rows": len(labelled_rows),
        "package_hash_contract": {"matching": sum(checks.values()), "total": len(checks), "checks": checks},
        "out_of_fold_model_metrics": model_metrics,
        "inspection_priority_ranking": rank_metrics(labelled_rows, list(config["top_k"])),
        "claim_boundary": config["claim_boundary"],
    }
    result["pass"] = (
        result["dataset_version"] == config["dataset_version"]
        and result["model_version"] == config["model_version"]
        and len(labelled_rows) == expected["timeline_rows"]
        and all(checks.values())
        and model_metrics == expected["out_of_fold_model_metrics"]
        and result["inspection_priority_ranking"] == expected["inspection_priority_ranking"]
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True)
    parser.add_argument(
        "--config",
        default=str(
            Path(__file__).resolve().parents[1]
            / "evaluation/solutionlink_readiness/canonical-v31-priority-replay-v1.json"
        ),
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = evaluate(Path(args.package_root), config)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
