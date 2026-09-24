"""Unit tests for llama_server_client._parse_body response parsing and startup safety."""

import http.server
import importlib
import os
import socket
import threading

import pytest

from lib import llama_server_client as lsc
from lib.llama_server_client import _parse_body
from lib.model_config import ModelConfig

_ELAPSED = 1_000_000_000  # 1 s in nanoseconds (arbitrary)


def test_llama_server_port_env_override(monkeypatch):
    """_PORT is read from LLAMA_SERVER_PORT at import time (see CLAUDE.md's pre-flight port-
    collision section, 2026-09-24) — reload the module with the env var set to prove the actual
    read path works, not just that _PORT can be monkeypatched directly."""
    monkeypatch.setenv("LLAMA_SERVER_PORT", "19191")
    try:
        reloaded = importlib.reload(lsc)
        assert reloaded._PORT == 19191
        assert reloaded._BASE_URL == "http://127.0.0.1:19191"
        assert reloaded._HEALTH_URL == "http://127.0.0.1:19191/health"
    finally:
        monkeypatch.delenv("LLAMA_SERVER_PORT", raising=False)
        importlib.reload(lsc)  # restore the default (8080) for every later test in this file


def test_llama_server_port_default_is_8080():
    assert lsc._PORT == 8080


def test_start_refuses_foreign_occupant(monkeypatch, tmp_path):
    """A pre-existing /health responder on our port (e.g. llm-service-provider's gateway,
    which also binds :8080) must raise loudly instead of being silently treated as our own
    freshly-started server (see next-runs.md, 2026-09-24)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", free_port), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(lsc, "_PORT", free_port)
        monkeypatch.setattr(lsc, "_BASE_URL", f"http://127.0.0.1:{free_port}")
        monkeypatch.setattr(lsc, "_HEALTH_URL", f"http://127.0.0.1:{free_port}/health")
        mgr = lsc.LlamaServerManager(models_dir=str(tmp_path))
        cfg = ModelConfig(ollama_name="x", gguf_file="x.gguf")
        with pytest.raises(RuntimeError, match="already serving something else"):
            mgr._start(cfg, 8192)
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


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
