#!/usr/bin/env python3
"""Paired, deterministic scheduling benchmark; no external provider calls.

Generation starts are potential provider requests, not actual billable calls.
Payload bytes are an input-size proxy, NOT tokenizer output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.evaluate_agent_review_generation_policy import evaluate, temporal_snapshots
from app.operations.agent_review_summary import compose_deterministic_agent_review_summary
from app.operations.agent_review_summary_provider import (
    AGENT_REVIEW_SUMMARY_SYSTEM_PROMPT,
    build_tool_selected_agent_review_summary_prompt_payload,
)


def run() -> dict:
    evaluation = evaluate()
    packets = {(scenario, index): packet for scenario, index, _, packet in temporal_snapshots()}
    prompt_bytes = {}
    for key, packet in packets.items():
        payload = build_tool_selected_agent_review_summary_prompt_payload(
            packet=packet, baseline_summary=compose_deterministic_agent_review_summary(packet),
        )
        prompt_bytes[key] = len(AGENT_REVIEW_SUMMARY_SYSTEM_PROMPT.encode('utf-8')) + len(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
        )
    policies = {}
    for policy in ('always', 'hybrid'):
        runs = evaluation['policies'][policy]['runs']
        starts = [(run['scenario'], event['snapshot']) for run in runs
                  for event in run['events'] if event['event'] == 'generation_started']
        bytes_total = sum(prompt_bytes[key] for key in starts)
        policies[policy] = {
            'generation_starts': len(starts),
            'simulated_input_prompt_utf8_bytes': bytes_total,
            'simulated_retries': evaluation['policies'][policy]['simulated_retries'],
            'critical_generation_requests': evaluation['policies'][policy]['critical_generation_requested'],
            'critical_count': evaluation['policies'][policy]['critical_count'],
            'simulated_exact_query_hits': evaluation['policies'][policy]['simulated_query_hits'],
            'simulated_query_count': evaluation['policies'][policy]['simulated_query_count'],
        }
    baseline, challenger = policies['always'], policies['hybrid']
    return {
        'evidence_level': 'deterministic_policy_simulation_with_prompt_byte_proxy',
        'snapshot_count': evaluation['fixture_snapshots'],
        'same_fixture_sha256': evaluation['fixture_sha256'],
        'provider_calls': None,
        'provider_reported_prompt_tokens': None,
        'provider_reported_completion_tokens': None,
        'cost': None,
        'note': 'No provider invoked. Bytes are serialized prompt size, not tokens. Fixed simulator failure and retry assumptions.',
        'policies': policies,
        'generation_start_reduction_fraction': 1 - challenger['generation_starts'] / baseline['generation_starts'],
        'simulated_prompt_byte_reduction_fraction': 1 - challenger['simulated_input_prompt_utf8_bytes'] / baseline['simulated_input_prompt_utf8_bytes'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
