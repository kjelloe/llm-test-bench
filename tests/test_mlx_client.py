"""MLX backend: lib/mlx_client.py against a stand-in mlx-lm server (stdlib HTTP), and bench.py --backend mlx end to end.

The stand-in answers like mlx-lm 0.32's server: message.content / message.reasoning, usage with
prompt_tokens_details.cached_tokens, /health and /v1/models. No Apple hardware or mlx package needed."""
import json
import platform
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from bench import mlx_order_independent
from lib import mlx_client
from lib.hw_snapshot import hw_summary
from lib.ollama_client import OllamaError

REPO = Path(__file__).resolve().parent.parent

CORRECT_CALC = '''BEGIN_FILE calc.py
def safe_div(a: float, b: float) -> float:
    """Divide a by b. Must raise ValueError (not ZeroDivisionError) when b is 0."""
    if b == 0:
        raise ValueError("division by zero")
    return a / b
END_FILE
'''


def _completion(content="hello", reasoning=None, usage=True, cached=0, finish="stop"):
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning"] = reasoning
    body = {"id": "x", "object": "chat.completion", "model": "default_model",
            "choices": [{"index": 0, "finish_reason": finish, "message": msg}]}
    if usage:
        body["usage"] = {"prompt_tokens": 900, "completion_tokens": 42, "total_tokens": 942,
                         "prompt_tokens_details": {"cached_tokens": cached}}
    return body


class StandIn:
    """One stand-in server per test; `reply` is what POST /v1/chat/completions returns next."""

    def __init__(self):
        self.reply = (200, _completion())
        self.delay = 0.0
        self.requests: list[dict] = []
        self.models = ["mlx-community/Qwen3-8B-4bit", "/Users/t/models/local-coder"]
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {"status": "ok"})
                elif self.path.startswith("/v1/models"):
                    self._send(200, {"object": "list", "data": [{"id": m} for m in outer.models]})
                else:
                    self._send(404, b"Not Found")

            def do_POST(self):
                outer.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                time.sleep(outer.delay)
                self._send(*outer.reply)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = StandIn()
    yield s
    s.close()


def _chat(server, **kw):
    args = dict(base_url=server.url, model="qwen3-8b", messages=[{"role": "user", "content": "hi"}],
                num_ctx=8192, temperature=0.0, seed=1, num_predict=400, timeout=5)
    return mlx_client.chat(**(args | kw))


def test_request_uses_mlx_fields_and_never_names_a_model(server):
    _chat(server, num_predict=1234, think=True)
    req = server.requests[0]
    assert req["model"] == "default_model"   # another name would make mlx-lm load (and download) that model
    assert req["max_tokens"] == 1234 and req["seed"] == 1 and req["temperature"] == 0.0 and req["top_p"] == 1.0
    assert req["chat_template_kwargs"] == {"enable_thinking": True} and req["stream"] is False
    assert not {"num_ctx", "options", "cache_prompt", "n_predict", "num_predict"} & set(req)


def test_valid_response_counts_and_honest_timing(server):
    server.reply = (200, _completion(content="BEGIN_FILE a\nEND_FILE", reasoning="thought", cached=0))
    resp = _chat(server)
    assert resp.content == "BEGIN_FILE a\nEND_FILE" and resp.thinking == "thought"
    assert resp.finish_reason == "stop"
    assert (resp.metrics.prompt_eval_count, resp.metrics.eval_count) == (900, 42)
    assert resp.metrics.eval_duration == 0 and resp.metrics.tok_per_s == 0.0   # never completion / request time
    assert resp.metrics.total_duration > 0
    assert resp.backend_notes["decode_timing"] == "unavailable"
    assert resp.backend_notes["cached_prompt_tokens"] == 0


def test_reasoning_only_answer_is_parsed_and_flagged(server):
    server.reply = (200, _completion(content=None, reasoning="BEGIN_FILE x\nEND_FILE"))
    resp = _chat(server)
    assert resp.content == "BEGIN_FILE x\nEND_FILE" and resp.thinking == ""
    assert resp.backend_notes["content_from_reasoning"] is True


def test_reasoning_while_off_is_flagged(server):
    server.reply = (200, _completion(content="BEGIN_FILE a\nEND_FILE", reasoning="thinking anyway"))
    assert _chat(server, think=False).backend_notes["reasoning_despite_off"] is True
    assert "reasoning_despite_off" not in _chat(server, think=True).backend_notes


def test_output_limit_reported(server):
    server.reply = (200, _completion(finish="length"))
    assert _chat(server).finish_reason == "length"


def test_missing_usage_is_unknown_not_zero_truncation(server):
    server.reply = (200, _completion(usage=False))
    resp = _chat(server)
    assert resp.metrics.prompt_eval_count == 0 and resp.backend_notes["usage"] == "missing"


def test_unsupported_controls_listed(server):
    resp = _chat(server, num_thread=10, thinking_budget=500)
    assert resp.backend_notes["unsupported"] == ["num_ctx", "num_thread", "thinking_budget"]
    assert resp.backend_notes["effective"]["enable_thinking"] is False


@pytest.mark.parametrize("reply, match", [
    ((500, {"error": "boom"}), "HTTP 500"),
    ((200, b"not json"), "malformed JSON"),
    ((200, {"choices": []}), "no choices"),
    ((200, {"choices": [{"index": 0}]}), "no message"),
])
def test_errors_become_ollama_errors(server, reply, match):
    server.reply = reply
    with pytest.raises(OllamaError, match=match):
        _chat(server)


def test_timeout(server):
    server.delay = 2.0
    with pytest.raises(OllamaError, match="Timed out"):
        _chat(server, timeout=1)


def test_connection_refused():
    with pytest.raises(OllamaError):
        mlx_client.chat(base_url="http://127.0.0.1:9", model="m", messages=[], timeout=2)
    with pytest.raises(OllamaError, match="cannot reach"):
        mlx_client.server_info("http://127.0.0.1:9", timeout=2)


def test_server_info_and_model_listed(server):
    info = mlx_client.server_info(server.url)
    assert info == {"health": "ok", "models": server.models}
    assert mlx_client.model_listed("mlx-community/Qwen3-8B-4bit", info["models"])
    assert mlx_client.model_listed("models/local-coder", info["models"])      # local dir, listed resolved
    assert not mlx_client.model_listed("mlx-community/Other-4bit", info["models"])


def test_order_independence_is_verified_from_cache_counts():
    rec = lambda n: {"backend_notes": {"cached_prompt_tokens": n}}
    assert mlx_order_independent([rec(0), rec(0)]) is True
    assert mlx_order_independent([rec(0), rec(17)]) is False
    assert mlx_order_independent([{"backend_notes": {}}, {}]) is None


def test_summary_names_the_inference_host_not_local_gpus():
    hw = {"gpu": [{"name": "NVIDIA GeForce RTX 4090", "vram_total_mb": 24564}], "cpu": "AMD Ryzen 9 9900X",
          "platform": "Linux 6.18", "inference_host": {
              "endpoint": "http://127.0.0.1:8085", "same_machine_as_tests": False,
              "host": {"chip": "Apple M3 Pro", "memory_gb": 36, "macos": "15.6", "mlx": "0.29.1", "mlx_lm": "0.32.2"}}}
    s = hw_summary(hw)
    assert "Apple M3 Pro 36 GB unified memory" in s and "mlx_lm 0.32.2" in s
    assert "4090" not in s and "VRAM" not in s
    del hw["inference_host"]["host"]
    assert "not recorded" in hw_summary(hw)


def test_bench_end_to_end_against_external_server(server, tmp_path):
    """bench.py grades a real task with the answer from the stand-in; it owns no server and records the split hosts."""
    server.reply = (200, _completion(content=CORRECT_CALC, cached=0))
    models = tmp_path / "test.mlx"
    models.write_text("qwen3-8b  -  max_ctx=8192  hf:mlx-community/Qwen3-8B-4bit\n")
    host = tmp_path / "mac.json"
    host.write_text(json.dumps({"chip": "Apple M3 Pro", "memory_gb": 36, "macos": "15.6"}))
    out = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, "bench.py", "--backend", "mlx", "--mlx-url", server.url, "--model-file", str(models),
         "--mlx-host-info", str(host), "--models", "qwen3-8b", "--tasks", "python_safe_div,context_16k",
         "--out", str(out)],
        cwd=REPO, capture_output=True, text=True, timeout=180,
        env={"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    data = json.loads(out.read_text())
    by_task = {r["task"]: r for r in data["results"]}
    rec = by_task["python_safe_div"]
    assert rec["tests_pass"] and rec["backend"] == "mlx" and rec["hf_repo"] == "mlx-community/Qwen3-8B-4bit"
    assert rec["tok_per_s"] == 0.0 and rec["metrics"]["eval_duration_ms"] is None
    assert rec["metrics"]["total_duration_ms"] > 0 and rec["gpu_snapshots"] is None
    assert by_task["context_16k"]["error_kind"] == "SKIPPED_CTX"     # max_ctx gates, not local VRAM
    inf = data["hardware"]["inference_host"]
    assert inf["model_listed"] is True and inf["declared_model"] == "mlx-community/Qwen3-8B-4bit"
    assert inf["same_machine_as_tests"] is (platform.system() == "Darwin")   # 127.0.0.1 on Linux = a tunnel
    assert inf["host"]["chip"] == "Apple M3 Pro"
    assert data["hardware"]["order_independent"] is True
    assert len(server.requests) == 1 and server.requests[0]["model"] == "default_model"


def test_bench_requires_url_and_one_model(tmp_path):
    run = lambda *a: subprocess.run([sys.executable, "bench.py", "--backend", "mlx", *a], cwd=REPO,
                                    capture_output=True, text=True, timeout=60,
                                    env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
    assert "--mlx-url" in run("--models", "m", "--tasks", "python_safe_div").stderr
    assert "exactly one model" in run("--mlx-url", "http://127.0.0.1:9", "--models", "a,b",
                                      "--tasks", "python_safe_div").stderr
