"""llama-server backend: process manager + OpenAI-compatible chat client.

Exposes chat() and unload_model() with the same signatures as ollama_client
so bench.py can select either backend at startup without changing call sites.

One llama-server process per benchmark run. The server is started (or restarted)
by LlamaServerManager.ensure() before each task when the model or ctx-size changes.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from lib.model_config import ModelConfig
from lib.ollama_client import OllamaError, OllamaMetrics, OllamaResponse

_PORT = 8080
_BASE_URL = f"http://127.0.0.1:{_PORT}"
_HEALTH_URL = f"{_BASE_URL}/health"


class LlamaServerManager:
    """Manages a single llama-server subprocess for the duration of a benchmark run."""

    def __init__(self, models_dir: str, bin_path: str = "llama-server") -> None:
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

    def ensure(self, cfg: ModelConfig, ctx_size: int, num_threads: int | None = None) -> None:
        """Start or restart the server if model changed or ctx grew. No-op if already suitable."""
        if not self.needs_restart(cfg, ctx_size):
            return
        self.stop()
        self._start(cfg, ctx_size, num_threads=num_threads)

    def stop(self) -> None:
        """Terminate the running server. No-op if not running."""
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._proc = None
        self._current_model = None
        self._current_ctx = 0

    def _start(self, cfg: ModelConfig, ctx_size: int,
               num_threads: int | None = None, startup_timeout: int = 120) -> None:
        if not cfg.gguf_file:
            raise ValueError(
                f"Model {cfg.ollama_name!r} has no GGUF file configured — "
                "required for llama-server backend"
            )
        gguf_path = self.models_dir / cfg.gguf_file
        if not gguf_path.exists():
            raise FileNotFoundError(f"GGUF file not found: {gguf_path}")

        cmd = [
            self.bin_path,
            "-m", str(gguf_path),
            "--ctx-size", str(ctx_size),
            "--port", str(_PORT),
            "--host", "127.0.0.1",
            "--n-gpu-layers", "999",
        ]
        if num_threads and num_threads > 0:
            cmd.extend(["--threads", str(num_threads)])
        for key, val in cfg.params.items():
            flag = "--" + key.replace("_", "-")
            if val is True:
                cmd.append(flag)
            else:
                cmd.extend([flag, str(val)])

        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._current_model = cfg.ollama_name
        self._current_ctx = ctx_size
        self._wait_ready(startup_timeout)

    def _wait_ready(self, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError("llama-server exited unexpectedly during startup")
            try:
                with urllib.request.urlopen(_HEALTH_URL, timeout=2) as r:
                    data = json.loads(r.read())
                    if data.get("status") == "ok":
                        return
            except Exception:
                pass
            time.sleep(1)
        self.stop()
        raise TimeoutError(f"llama-server did not become ready within {timeout}s")


def chat(
    base_url: str,
    model: str,                   # unused: llama-server is single-model per process
    messages: list[dict],
    num_ctx: int = 8192,          # unused: set at server startup via LlamaServerManager
    temperature: float = 0.0,
    seed: int = 1,
    num_predict: int = 400,
    timeout: int = 300,
    think: bool = False,          # unsupported by llama-server
    num_thread: int | None = None,  # unused: set at server startup
    keep_alive: str | int | None = None,  # unused: no Ollama keep_alive concept
) -> OllamaResponse:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload: dict = {
        "messages": messages,
        "temperature": temperature,
        "seed": seed,
        "max_tokens": num_predict,
        "stream": False,
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

    elapsed_ns = int((time.monotonic() - t_start) * 1e9)

    choice = (body.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "")
    usage = body.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    return OllamaResponse(
        content=content,
        thinking="",
        metrics=OllamaMetrics(
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            prompt_eval_duration=0,
            eval_duration=elapsed_ns,   # wall time as proxy; prompt-eval not separated
            total_duration=elapsed_ns,
        ),
    )


def unload_model(base_url: str, model: str, timeout: int = 30) -> None:
    """No-op: lifecycle is managed by LlamaServerManager.stop()."""
    pass
