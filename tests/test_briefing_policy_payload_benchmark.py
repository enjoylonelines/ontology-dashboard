from scripts.benchmark_briefing_policy_payload import run


def test_paired_policy_payload_benchmark_is_deterministic_and_explicit_about_missing_usage():
    first = run()
    assert run() == first
    assert first['snapshot_count'] == 80
    assert first['policies']['always']['generation_starts'] == 62
    assert first['policies']['hybrid']['generation_starts'] == 56
    assert first['policies']['always']['critical_generation_requests'] == 40
    assert first['policies']['hybrid']['critical_generation_requests'] == 40
    assert first['policies']['hybrid']['simulated_input_prompt_utf8_bytes'] < first['policies']['always']['simulated_input_prompt_utf8_bytes']
    assert first['provider_calls'] is None
    assert first['provider_reported_prompt_tokens'] is None
    assert first['provider_reported_completion_tokens'] is None
    assert first['cost'] is None
