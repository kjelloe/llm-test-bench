"""vLLM backend: process manager + OpenAI-compatible chat client.

Exposes chat() and unload_model() with the same signatures as ollama_client
and llama_server_client so bench.py can select any backend at startup without
changing call sites.

One 'vllm serve' process per model. The server is started (or restarted) by
VLLMManager.ensure() before each task when the model or ctx-size changes.

Model files (.vllm):
  short-name  gguf-file  params  hf:tokenizer-repo
  params: tp=2, dtype=auto, max_model_len=N (harness cap), enforce_eager
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from lib.model_config import ModelConfig
from lib.ollama_client import OllamaError, OllamaMetrics, OllamaResponse

# model-file key → vllm CLI flag name
_PARAM_NAME_MAP: dict[str, str] = {
    "tp": "tensor-parallel-size",
    "gpu_mem_util": "gpu-memory-utilization",
    "max_num_seqs": "max-num-seqs",
}

# Params consumed by the harness; never forwarded to vllm serve
_HARNESS_ONLY: set[str] = {"thinking", "max_ctx", "max_model_len"}

_PORT = 8090
_BASE_URL = f"http://127.0.0.1:{_PORT}"
_HEALTH_URL = f"{_BASE_URL}/health"


class VLLMManager:
    """Manages a single vllm serve subprocess for the duration of a benchmark run.

    Interface mirrors LlamaServerManager exactly so bench.py needs no
    backend-specific branching beyond the initial setup block.
    """

    def __init__(self, models_dir: str, bin_path: str = "vllm") -> None:
        self.models_dir = Path(models_dir)
        self.bin_path = bin_path
        self._proc: subprocess.Popen | None = None
        self._current_model: str | None = None
        self._current_ctx: int = 0

    @property
    def base_url(self) -> str:
        return _BASE_URL

    def needs_restart(self, cfg: ModelConfig, ctx_size: int) -> bool:
        return (
            self._proc is None
            or self._proc.poll() is not None
            or self._current_model != cfg.ollama_name
            or ctx_size > self._current_ctx
        )

    def ensure(self, cfg: ModelConfig, ctx_size: int,
               num_threads: int | None = None, startup_timeout: int = 600) -> None:
        """Start or restart the server if model changed or ctx grew. No-op if suitable."""
        if not self.needs_restart(cfg, ctx_size):
            return
        self.stop()
        self._start(cfg, ctx_size, startup_timeout=startup_timeout)

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        if self._proc.stderr:
            try:
                self._proc.stderr.close()
            except Exception:
                pass
        self._proc = None
        self._current_model = None
        self._current_ctx = 0

    def _start(self, cfg: ModelConfig, ctx_size: int, startup_timeout: int = 600) -> None:
        if not cfg.gguf_file:
            raise ValueError(
                f"Model {cfg.ollama_name!r} has no GGUF file configured — "
                "required for vllm backend (set gguf-file field in .vllm model file)"
            )
        gguf_path = self.models_dir / cfg.gguf_file
        if not gguf_path.exists():
            raise FileNotFoundError(f"GGUF file not found: {gguf_path}")
        if not cfg.hf_repo:
            raise ValueError(
                f"Model {cfg.ollama_name!r} has no hf: field — "
                "required for vllm GGUF mode (used as --tokenizer source)"
            )

        cmd = [
            self.bin_path, "serve", str(gguf_path),
            "--tokenizer", cfg.hf_repo,
            "--load-format", "gguf",
            "--max-model-len", str(ctx_size),
            "--served-model-name", cfg.ollama_name,
            "--port", str(_PORT),
            "--host", "127.0.0.1",
        ]
        for key, val in cfg.params.items():
            if key in _HARNESS_ONLY:
                continue
            cli_key = _PARAM_NAME_MAP.get(key, key.replace("_", "-"))
            flag = f"--{cli_key}"
            if val is True:
                cmd.append(flag)
            else:
                cmd.extend([flag, str(val).replace("|", ",")])

        # Propagate HF token for gated models (e.g. meta-llama/Llama-3.3).
        # Falls back to hf-token.txt in the repo root if HF_TOKEN is not set.
        env = os.environ.copy()
        if not env.get("HF_TOKEN") and not env.get("HUGGING_FACE_HUB_TOKEN"):
            _token_file = Path(__file__).parent.parent / "hf-token.txt"
            if _token_file.exists():
                _token = _token_file.read_text(encoding="utf-8").strip()
                if _token:
                    env["HF_TOKEN"] = _token

        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env,
        )
        self._current_model = cfg.ollama_name
        self._current_ctx = ctx_size
        try:
            self._wait_ready(startup_timeout)
        except Exception:
            self._current_model = None
            self._current_ctx = 0
            raise

    def _wait_ready(self, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                stderr_out = ""
                if self._proc.stderr:
                    try:
                        stderr_out = self._proc.stderr.read().decode(errors="replace").strip()
                    except Exception:
                        pass
                msg = "vllm serve exited unexpectedly during startup"
                if stderr_out:
                    msg += f"\n--- stderr ---\n{stderr_out[-3000:]}"
                raise RuntimeError(msg)
            try:
                with urllib.request.urlopen(_HEALTH_URL, timeout=2) as r:
                    if r.status == 200:
                        return
            except Exception:
                pass
            time.sleep(2)
        self.stop()
        raise TimeoutError(f"vllm serve did not become ready within {timeout}s")


def _parse_body(body: dict, elapsed_ns: int) -> OllamaResponse:
    """Parse an OpenAI-compatible /v1/chat/completions response from vLLM."""
    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    # vLLM may surface reasoning in reasoning_content for supported models
    thinking = msg.get("reasoning_content") or ""
    if not content and thinking:
        content = thinking
        thinking = ""
    finish_reason = choice.get("finish_reason") or ""

    usage = body.get("usage") or {}
    prompt_tokens     = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    # vLLM does not expose llama.cpp-style timings; fall back to wall time.
    return OllamaResponse(
        content=content,
        thinking=thinking,
        finish_reason=finish_reason,
        metrics=OllamaMetrics(
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            prompt_eval_duration=0,
            eval_duration=elapsed_ns,
            total_duration=elapsed_ns,
        ),
    )


def chat(
    base_url: str,
    model: str,
    messages: list[dict],
    num_ctx: int = 8192,
    temperature: float = 0.0,
    seed: int = 1,
    num_predict: int = 400,
    timeout: int = 300,
    think: bool = False,
    thinking_budget: int | None = None,
    num_thread: int | None = None,
    keep_alive: str | int | None = None,
) -> OllamaResponse:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "seed": seed,
        "max_tokens": num_predict,
        "stream": False,
        "top_p": 1.0,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t_start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise OllamaError(f"HTTP {exc.code}: {exc.read().decode()[:200]}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"URL error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaError(f"Timed out after {timeout}s") from exc
    except (ConnectionError, OSError) as exc:
        raise OllamaError(f"Connection error (server crash/OOM?): {exc}") from exc

    elapsed_ns = int((time.monotonic() - t_start) * 1e9)
    return _parse_body(body, elapsed_ns)


def unload_model(base_url: str, model: str, timeout: int = 30) -> None:
    """No-op: lifecycle is managed by VLLMManager.stop()."""
    pass
