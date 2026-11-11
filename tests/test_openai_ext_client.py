"""--backend openai-ext: lib/openai_ext_client.py against the MLX tests' stand-in OpenAI server, and bench.py end to end."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib import openai_ext_client as ext
from lib.ollama_client import OllamaError
from tests.test_mlx_client import CORRECT_CALC, StandIn, _completion

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def server():
    s = StandIn()
    s.models = ["strata/gemma-4-31b-it"]
    yield s
    s.close()


def _chat(server, **kw):
    args = dict(base_url=server.url, model="strata/gemma-4-31b-it", messages=[{"role": "user", "content": "hi"}],
                num_ctx=8192, temperature=0.0, seed=1, num_predict=400, timeout=5)
    return ext.chat(**(args | kw))


def test_request_is_greedy_and_names_the_served_model(server):
    ext.chat_as("strata/gemma-4-31b-it", base_url=server.url, model="gemma4:31b", messages=[], timeout=5)
    req = server.requests[0]
    assert req["model"] == "strata/gemma-4-31b-it"
    assert req["temperature"] == 0 and req["top_p"] == 1.0 and req["seed"] == 1 and req["stream"] is False
    assert req["chat_template_kwargs"] == {"enable_thinking": False}


def test_timings_give_decode_speed_when_sent(server):
    body = _completion() | {"timings": {"predicted_per_second": 21.0, "prompt_ms": 300.0}}
    server.reply = (200, body)
    resp = _chat(server)
    assert resp.metrics.tok_per_s == pytest.approx(21.0, rel=1e-3)
    assert resp.metrics.prompt_eval_duration == 300_000_000
    assert "decode_timing" not in resp.backend_notes


def test_no_timings_means_no_speed(server):
    resp = _chat(server)
    assert resp.metrics.tok_per_s == 0 and resp.backend_notes["decode_timing"] == "unavailable"


def test_reasoning_content_while_off_is_flagged(server):
    body = _completion()
    body["choices"][0]["message"]["reasoning_content"] = "let me think"
    server.reply = (200, body)
    resp = _chat(server)
    assert resp.thinking == "let me think" and resp.backend_notes["reasoning_despite_off"]


def test_served_model_choice():
    assert ext.served_model(["a"], None) == "a"
    assert ext.served_model(["a", "b"], "b") == "b"
    with pytest.raises(OllamaError, match="--ext-model"):
        ext.served_model(["a", "b"], None)
    with pytest.raises(OllamaError, match="not in"):
        ext.served_model(["a"], "c")


def _bench(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "bench.py", "--backend", "openai-ext", *args],
        cwd=REPO, capture_output=True, text=True, timeout=180,
        env={"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "HOME": str(tmp_path)},
    )


def test_bench_end_to_end(server, tmp_path):
    server.reply = (200, _completion(content=CORRECT_CALC, cached=0)
                    | {"timings": {"predicted_per_second": 30.0}})
    models = tmp_path / "strata.txt"
    models.write_text("gemma4:31b-strata  -  max_ctx=8192  hf:google/gemma-4-31b-it\n")
    out = tmp_path / "r.json"
    proc = _bench(tmp_path, "--ext-url", server.url, "--ext-label", "strata 0.1.48 abc1234",
                  "--model-file", str(models), "--models", "gemma4:31b-strata",
                  "--tasks", "python_safe_div,context_16k", "--out", str(out))
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    data = json.loads(out.read_text())
    by_task = {r["task"]: r for r in data["results"]}
    rec = by_task["python_safe_div"]
    assert rec["tests_pass"] and rec["backend"] == "openai-ext" and rec["model"] == "gemma4:31b-strata"
    assert rec["tok_per_s"] == pytest.approx(30.0, rel=1e-2)
    assert by_task["context_16k"]["error_kind"] == "SKIPPED_CTX"
    hw = data["hardware"]
    assert hw["server_name"] == "strata" and hw["llama_server_version"] == "0.1.48 abc1234"
    assert hw["ext_served_model"] == "strata/gemma-4-31b-it" and "inference_host" not in hw
    assert hw["order_independent"] is True
    assert server.requests[-1]["model"] == "strata/gemma-4-31b-it"


def test_bench_requires_url_label_and_one_model(server, tmp_path):
    assert "--ext-url" in _bench(tmp_path, "--models", "m", "--tasks", "python_safe_div").stderr
    assert "--ext-label" in _bench(tmp_path, "--ext-url", server.url, "--models", "m",
                                   "--tasks", "python_safe_div").stderr
    assert "exactly one model" in _bench(tmp_path, "--ext-url", server.url, "--ext-label", "strata x",
                                         "--models", "a,b", "--tasks", "python_safe_div").stderr
