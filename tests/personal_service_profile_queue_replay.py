"""Service-profile queue replay using explicitly synthetic provider latency.

Uses documented 10s watch cycle, 100/500/1000 assets and 1/10/50% changes.
Historical aggregate p50/p95 are reference anchors, NOT reconstructed live samples.
"""
from __future__ import annotations
import json
from pathlib import Path
from scripts.evaluate_briefing_scalability import ProviderReference, challenger_projection

ROOT = Path(__file__).resolve().parents[1]


def run():
    historic = json.loads((ROOT/"docs/eval/engineering-foundations/briefing-scalability-2026-09-20.json").read_text())
    p50 = historic["provider_reference"]["latency_ms"]["p50"]
    p95 = historic["provider_reference"]["latency_ms"]["p95"]
    # Synthetic two-point distribution only; not the missing 120 individual measurements.
    provider = ProviderReference(
        provider="synthetic", model="two-point-latency", latency_samples_ms=(p50,)*19+(p95,),
        prompt_token_samples=(0,)*20, completion_token_samples=(0,)*20,
        total_token_samples=(0,)*20, latency_basis="synthetic historical aggregate anchors",
        token_basis="not modeled", cost_status="not_measured",
    )
    rows = []
    for assets in (100,500,1000):
        for label, fraction in (("low",.01),("medium",.10),("burst",.50)):
            for workers in (2,4,8):
                result = challenger_projection(
                    asset_count=assets, changed_count=round(assets*fraction),
                    detection_ms=0.743, poll_interval_ms=10000,
                    provider=provider, workers=workers, cycles=6,
                )
                rows.append({
                    "assets":assets, "change_profile":label, "workers":workers,
                    "candidate_events":result["candidate_events"],
                    "generated":result["generated_count"],
                    "coalesced":result["coalesced_candidate_count"],
                    "dropped":result["dropped_candidate_count"],
                    "queue_wait_p95_ms":result["queue_wait_ms"]["p95"],
                    "end_to_end_p95_ms":result["end_to_end_ms"]["p95"],
                    "queue_depth_max":result["queue_depth"]["max"],
                    "latest_materialization_rate":result.get("latest_changed_asset_materialization_rate"),
                })
    payload = {"method":"deterministic discrete-event simulation; synthetic provider latency based on historical p50/p95 only; not PostgreSQL, not live LLM, not production SLO",
               "poll_seconds":10,"cycles":6,"provider_latency_anchor_ms":{"p50":p50,"p95":p95},
               "rows":rows}
    output = ROOT/"docs/evidence/2026-11-05-service-profile-queue-replay.json"
    output.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"rows":len(rows),"output":str(output.relative_to(ROOT)),
                      "worst_queue_wait_p95_ms":max(r["queue_wait_p95_ms"] for r in rows),
                      "worst_end_to_end_p95_ms":max(r["end_to_end_p95_ms"] for r in rows),
                      "sample_1000": [r for r in rows if r["assets"]==1000]},ensure_ascii=False))


if __name__ == "__main__":
    run()
