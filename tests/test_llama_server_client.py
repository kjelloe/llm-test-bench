"""Unit tests for llama_server_client._parse_body response parsing."""

from lib.llama_server_client import _parse_body

_ELAPSED = 1_000_000_000  # 1 s in nanoseconds (arbitrary)


def test_reasoning_content_fallback():
    """When content is empty, reasoning_content is used as the answer."""
    body = {
        "choices": [{"message": {
            "content": "",
            "reasoning_content": "BEGIN_FILE calc.py\npass\nEND_FILE\n",
        }}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.content == "BEGIN_FILE calc.py\npass\nEND_FILE\n"
    assert resp.thinking == ""


def test_content_wins_when_present():
    """When content is non-empty, it is used and reasoning_content goes to thinking."""
    body = {
        "choices": [{"message": {
            "content": "BEGIN_FILE calc.py\npass\nEND_FILE\n",
            "reasoning_content": "let me think...",
        }}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.content == "BEGIN_FILE calc.py\npass\nEND_FILE\n"
    assert resp.thinking == "let me think..."


def test_both_empty():
    """Both content and reasoning_content absent → empty content, empty thinking."""
    body = {"choices": [{"message": {}}], "usage": {}}
    resp = _parse_body(body, _ELAPSED)
    assert resp.content == ""
    assert resp.thinking == ""


def test_finish_reason_captured():
    """finish_reason is read from choices[0].finish_reason."""
    body = {
        "choices": [{"finish_reason": "length", "message": {"content": "x"}}],
        "usage": {},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.finish_reason == "length"


def test_finish_reason_absent_is_empty():
    """finish_reason defaults to empty string when not present."""
    body = {"choices": [{"message": {"content": "x"}}], "usage": {}}
    resp = _parse_body(body, _ELAPSED)
    assert resp.finish_reason == ""


def test_timings_used_when_present():
    """predicted_ms timing is used when predicted_per_second is absent."""
    body = {
        "choices": [{"message": {"content": "x"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "timings": {"predicted_ms": 500.0, "prompt_ms": 100.0},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.metrics.eval_duration == 500_000_000
    assert resp.metrics.prompt_eval_duration == 100_000_000


def test_predicted_per_second_preferred_over_ms():
    """predicted_per_second wins over predicted_ms when both are present."""
    # 20 tokens at 100 tok/s → 200 ms → 200_000_000 ns
    body = {
        "choices": [{"message": {"content": "x"}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 20},
        "timings": {
            "predicted_ms": 0.0,        # would give wrong answer if used
            "predicted_per_second": 100.0,
            "prompt_ms": 5000.0,
        },
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.metrics.eval_duration == 200_000_000
    assert resp.metrics.prompt_eval_duration == 5_000_000_000


def test_predicted_per_second_fixes_zero_ms_fallback():
    """When predicted_ms=0 (short context-task generation), predicted_per_second gives the correct rate."""
    # Without this fix the old code fell back to wall-clock elapsed_ns (1 s),
    # giving 20 / 1 = 20 tok/s instead of the actual 115 tok/s.
    body = {
        "choices": [{"message": {"content": "x"}}],
        "usage": {"prompt_tokens": 32768, "completion_tokens": 20},
        "timings": {"predicted_ms": 0.0, "predicted_per_second": 115.0},
    }
    resp = _parse_body(body, _ELAPSED)
    # 20 / 115 * 1e9 ≈ 173_913_043
    assert abs(resp.metrics.eval_duration - 173_913_043) < 10
    # tok_per_s should now reflect the server-reported rate, not wall-clock
    assert abs(resp.metrics.tok_per_s - 115.0) < 0.1


def test_fallback_to_wall_when_no_timings():
    """Without any timing fields, eval_duration falls back to elapsed_ns."""
    body = {
        "choices": [{"message": {"content": "x"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.metrics.eval_duration == _ELAPSED
