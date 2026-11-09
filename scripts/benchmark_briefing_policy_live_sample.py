#!/usr/bin/env python3
"""Bounded live provider sample of matched policy schedules.

Only selected unique snapshot keys are called. Do not extrapolate sample usage
to the entire timeline as measured billing. Never persist provider prose.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from scripts.evaluate_agent_review_generation_policy import evaluate, temporal_snapshots
from app.infra.llm.provider import OpenAICompatibleProvider
from app.operations.agent_review_summary import compose_deterministic_agent_review_summary
from app.operations.agent_review_summary_provider import (
    AGENT_REVIEW_SUMMARY_SYSTEM_PROMPT,
    agent_review_summary_editable_schema,
    build_tool_selected_agent_review_summary_prompt_payload,
)


def choose_sample(report, max_calls):
    starts = {}
    for policy in ('always', 'hybrid'):
        starts[policy] = Counter((run['scenario'], event['snapshot']) for run in report['policies'][policy]['runs']
                                 for event in run['events'] if event['event'] == 'generation_started')
    union = sorted(starts['always'] | starts['hybrid'])
    shared = [key for key in union if starts['always'][key] and starts['hybrid'][key]]
    only_always = [key for key in union if starts['always'][key] and not starts['hybrid'][key]]
    only_hybrid = [key for key in union if starts['hybrid'][key] and not starts['always'][key]]
    # Cover both arms and differing schedules; shared calls count once.
    chosen = []
    groups = (only_always, only_hybrid, shared)
    while len(chosen) < max_calls and any(groups):
        for group in groups:
            if group and len(chosen) < max_calls:
                chosen.append(group.pop(0))
    return chosen, starts


def run(max_calls: int):
    if not 1 <= max_calls <= 20:
        raise ValueError('max_calls must be between 1 and 20')
    load_dotenv(Path('.env'), override=False)
    provider = OpenAICompatibleProvider()
    if not provider.api_key or not provider.model:
        raise RuntimeError('live provider credentials/model missing')
    report = evaluate()
    chosen, starts = choose_sample(report, max_calls)
    packets = {(s, i): packet for s, i, _, packet in temporal_snapshots()}
    rows = []
    raw_requests = 0
    original_post = provider._post_chat_completion

    def metered_post(body):
        nonlocal raw_requests
        if raw_requests >= max_calls:
            raise RuntimeError('hard live request cap reached')
        raw_requests += 1
        return original_post(body)

    provider._post_chat_completion = metered_post
    for scenario, index in chosen:
        if raw_requests >= max_calls:
            break
        packet = packets[(scenario, index)]
        payload = build_tool_selected_agent_review_summary_prompt_payload(
            packet=packet, baseline_summary=compose_deterministic_agent_review_summary(packet),
        )
        started = time.monotonic()
        usage, status, error_type = None, 'ok', None
        try:
            result = provider.generate_json_with_metadata(
                AGENT_REVIEW_SUMMARY_SYSTEM_PROMPT, payload,
                response_schema=agent_review_summary_editable_schema(),
                response_schema_name='agent_review_summary_editable',
            )
            usage = result.get('provider_metadata', {}).get('usage')
        except Exception as exc:
            status, error_type = 'error', type(exc).__name__
        rows.append({
            'scenario': scenario, 'snapshot_index': index,
            'always_start_count': starts['always'][(scenario, index)],
            'hybrid_start_count': starts['hybrid'][(scenario, index)],
            'status': status, 'error_type': error_type,
            'usage': usage,
            'elapsed_ms': round((time.monotonic() - started) * 1000, 2),
        })
        # Authentication or transport failures are not useful to repeat.
        if status != 'ok':
            break
    return {
        'evidence_level': 'live_provider_bounded_snapshot_sample',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'model': provider.model,
        'endpoint_host': __import__('urllib.parse', fromlist=['urlparse']).urlparse(provider.base_url).hostname,
        'max_raw_http_requests': max_calls,
        'actual_raw_http_requests': raw_requests,
        'selected_unique_snapshot_count': len(chosen),
        'completed_snapshot_count': len(rows),
        'full_timeline_generation_starts': {p: sum(starts[p].values()) for p in ('always', 'hybrid')},
        'note': 'Same snapshot uses one shared provider sample for both policies. Sample is NOT full paired live replay; no token/cost reduction is claimed for full workload. Provider prose discarded. On error, stop.',
        'rows': rows,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-calls', type=int, default=20)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.max_calls)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'actual_raw_http_requests': result['actual_raw_http_requests'],
        'completed_snapshot_count': result['completed_snapshot_count'],
        'statuses': Counter(r['status'] for r in result['rows']),
        'usage_total': {key: sum((r['usage'] or {}).get(key, 0) for r in result['rows'])
                        for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
    }, ensure_ascii=False, default=dict))
