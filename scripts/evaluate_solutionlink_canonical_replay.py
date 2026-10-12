#!/usr/bin/env python3
"""Read-only integrity and freshness evaluation for a frozen Canonical replay cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _cohort_fingerprint(rows: list[dict[str, Any]]) -> str:
    fields = ("artifact_id", "prediction_id", "prediction_result_id", "asset_id", "observed_at", "status_grade", "schema_version", "model_version", "source_sha256")
    canonical = [
        {field: _timestamp(row[field]).isoformat() if field == "observed_at" else row[field] for field in fields}
        for row in rows
    ]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fresh(row: dict[str, Any], as_of: datetime, hours: int) -> bool:
    observed_at = _timestamp(row["observed_at"])
    return 0 <= (as_of - observed_at).total_seconds() <= hours * 3600


def evaluate(root: Path, database_url: str) -> dict[str, Any]:
    config_path = root / "evaluation" / "solutionlink_readiness" / "canonical-v31-replay-cohort-v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected = config["expected"]
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT artifact_id,prediction_id,prediction_result_id,asset_id,observed_at,
                       status_grade,schema_version,model_version,source_sha256,provenance
                FROM pm_result_artifacts
                WHERE dataset_version_id=%s
                ORDER BY artifact_id ASC
                LIMIT %s
                """,
                (config["dataset_version_id"], config["selection"]["limit"]),
            )
            rows = list(cursor.fetchall())

    required = ("artifact_id", "prediction_id", "prediction_result_id", "asset_id", "observed_at", "source_sha256")
    missing_reference_fields = {
        row["artifact_id"]: [field for field in required if not row.get(field)]
        for row in rows
    }
    missing_reference_fields = {key: value for key, value in missing_reference_fields.items() if value}
    historical_as_of = _timestamp(config["historical_as_of"])
    current_as_of = _timestamp(config["current_as_of"])
    historical_fresh = [row for row in rows if _fresh(row, historical_as_of, config["freshness_hours"])]
    current_fresh = [row for row in rows if _fresh(row, current_as_of, config["freshness_hours"])]
    source_type_matches = [
        isinstance(row["provenance"], dict)
        and row["provenance"].get("source_type") == "derived_result_artifact"
        and row["provenance"].get("dataset_version") == config["dataset_version"]
        and row["provenance"].get("canonical_source_mutated") is False
        for row in rows
    ]
    source_hashes = sorted({row["source_sha256"] for row in rows})
    schema_versions = sorted({row["schema_version"] for row in rows})
    model_versions = sorted({row["model_version"] for row in rows})
    cohort_fingerprint = _cohort_fingerprint(rows)
    result = {
        "suite_id": config["schema_version"],
        "fixture_kind": config["source_kind"],
        "dataset_version_id": config["dataset_version_id"],
        "selection": config["selection"],
        "artifact_count": len(rows),
        "cohort_fingerprint_sha256": cohort_fingerprint,
        "reference_completeness": {"complete": len(rows) - len(missing_reference_fields), "total": len(rows), "missing": missing_reference_fields},
        "provenance_contract": {"matching": sum(source_type_matches), "total": len(rows)},
        "historical_freshness": {"as_of": config["historical_as_of"], "fresh": len(historical_fresh), "total": len(rows)},
        "current_freshness": {"as_of": config["current_as_of"], "fresh": len(current_fresh), "total": len(rows)},
        "schema_versions": schema_versions,
        "model_versions": model_versions,
        "source_hashes": source_hashes,
        "claim_boundary": config["claim_boundary"],
    }
    result["pass"] = (
        len(rows) == expected["artifact_count"]
        and not missing_reference_fields
        and all(source_type_matches)
        and schema_versions == [expected["schema_version"]]
        and model_versions == [expected["model_version"]]
        and source_hashes == [expected["source_sha256"]]
        and cohort_fingerprint == expected["cohort_fingerprint_sha256"]
        and len(historical_fresh) == len(rows)
        and len(current_fresh) == 0
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = evaluate(Path(args.root), args.database_url)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
