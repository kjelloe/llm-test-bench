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
import socket
import subprocess
import tempfile
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

    def __init__(self, models_dir: str, bin_path: str = "vllm",
                 debug: bool = False) -> None:
        self.models_dir = Path(models_dir)
        self.bin_path = bin_path
        self.debug = debug
        self._proc: subprocess.Popen | None = None
        self._current_model: str | None = None
        self._current_ctx: int = 0
        self._log_path: str | None = None
        self._last_cmd: list[str] = []
        self._effective_base_url: str = _BASE_URL

    @property
    def base_url(self) -> str:
        return self._effective_base_url

    def needs_restart(self, cfg: ModelConfig, ctx_size: int) -> bool:
        return (
            self._proc is None
            or self._proc.poll() is not None
            or self._current_model != cfg.ollama_name
            or ctx_size > self._current_ctx
        )

    # vLLM startup is slower than llama-server: FlashInfer JIT warmup adds
    # ~100s even with a warm cache, and cold first-run compilation can take
    # several minutes. Never allow less than 20 minutes.
    _MIN_STARTUP_TIMEOUT = 1200

    def ensure(self, cfg: ModelConfig, ctx_size: int,
               num_threads: int | None = None, startup_timeout: int = 600) -> None:
        """Start or restart the server if model changed or ctx grew. No-op if suitable."""
        if not self.needs_restart(cfg, ctx_size):
            return
        self.stop()
        self._start(cfg, ctx_size, startup_timeout=max(startup_timeout, self._MIN_STARTUP_TIMEOUT))

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._proc = None
        self._current_model = None
        self._current_ctx = 0
        self._effective_base_url = _BASE_URL
        if self._log_path and os.path.exists(self._log_path):
            try:
                os.unlink(self._log_path)
            except Exception:
                pass
            self._log_path = None

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
            "--host", "0.0.0.0",
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

        # Ensure .venv/bin is on PATH so flashinfer JIT can find the ninja
        # binary installed by the ninja Python package (pip install ninja).
        # Without this the EngineCore subprocess inherits the caller's PATH,
        # which may not include the venv bin directory.
        _venv_bin = str(Path(self.bin_path).parent)
        if _venv_bin not in env.get("PATH", ""):
            env["PATH"] = _venv_bin + os.pathsep + env.get("PATH", "")

        self._last_cmd = cmd
        if self.debug:
            # Inherit terminal — output streams live; useful for startup diagnosis.
            self._proc = subprocess.Popen(cmd, env=env)
        else:
            # Write stdout+stderr to a temp file so both crash and timeout paths
            # can read the log regardless of whether the process is still running.
            _log_fd, self._log_path = tempfile.mkstemp(suffix=".log", prefix="vllm-")
            _log_file = os.fdopen(_log_fd, "wb")
            self._proc = subprocess.Popen(cmd, stdout=_log_file, stderr=_log_file, env=env)
            _log_file.close()  # Popen holds its own fd; we close our copy
        self._current_model = cfg.ollama_name
        self._current_ctx = ctx_size
        try:
            self._wait_ready(startup_timeout)
            self._effective_base_url = self._detect_connect_url()
        except Exception:
            self._current_model = None
            self._current_ctx = 0
            raise

    def _read_log(self, tail: int = 8000) -> str:
        if not self._log_path:
            return ""
        try:
            with open(self._log_path, errors="replace") as f:
                content = f.read()
            return content[-tail:] if len(content) > tail else content
        except Exception:
            return ""

    def _detect_connect_url(self) -> str:
        """Find which URL can actually reach the server.

        WSL2 networkingMode=mirrored routes 127.0.0.1 through the Windows
        network stack where Windows Firewall may drop connections (ETIMEDOUT).
        The machine's primary LAN IP bypasses this and reaches the server
        directly (vllm binds to 0.0.0.0, so all interfaces are covered).
        """
        candidates = [f"http://127.0.0.1:{_PORT}"]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as _s:
                _s.connect(("8.8.8.8", 80))
                _ip = _s.getsockname()[0]
            if _ip and _ip != "127.0.0.1":
                candidates.append(f"http://{_ip}:{_PORT}")
        except Exception:
            pass
        for url in candidates:
            try:
                with urllib.request.urlopen(f"{url}/health", timeout=2) as r:
                    if r.status == 200:
                        if url != _BASE_URL and self.debug:
                            print(f"  [vllm] using {url} (127.0.0.1 is unreachable)", flush=True)
                        return url
            except Exception:
                continue
        return _BASE_URL  # fallback: chat() will surface a clear network error

    def _wait_ready(self, timeout: int) -> None:
        cmd_str = " ".join(self._last_cmd)
        deadline = time.monotonic() + timeout
        last_err = ""
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                msg = f"vllm serve exited unexpectedly during startup\n  cmd: {cmd_str}"
                if not self.debug:
                    log = self._read_log()
                    if log:
                        msg += f"\n--- vllm log ---\n{log}"
                raise RuntimeError(msg)
            # Log-based readiness: parse uvicorn's startup banner from the temp log file.
            # This is the primary readiness signal in non-debug mode because HTTP health
            # checks time out on WSL2 networkingMode=mirrored (loopback is routed through
            # the Windows network stack where it may be firewalled).
            if not self.debug and "Application startup complete." in self._read_log():
                return
            try:
                # HTTP health check: fast path for non-WSL-mirrored environments.
                with urllib.request.urlopen(_HEALTH_URL, timeout=5) as r:
                    if r.status == 200:
                        return
                    last_err = f"HTTP {r.status}"
            except Exception as exc:
                last_err = repr(exc)
                if self.debug:
                    elapsed = timeout - max(0.0, deadline - time.monotonic())
                    print(f"  [vllm] health check ({elapsed:.0f}s): {exc}", flush=True)
            time.sleep(2)
        msg = (
            f"vllm serve did not become ready within {timeout}s\n"
            f"  cmd: {cmd_str}\n"
            f"  last health-check error: {last_err or '(no response yet)'}"
        )
        if not self.debug:
            log = self._read_log()
            if log:
                msg += f"\n--- vllm log (last 8000 chars) ---\n{log}"
        self.stop()
        raise TimeoutError(msg)


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
    # vLLM enforces prompt_tokens + max_tokens <= max_model_len at request time.
    # Reserve 512 tokens for the prompt as an initial guess; tasks with large
    # prompts (e.g. csv_nordic_property with a 5k-row CSV) may need more headroom.
    # On HTTP 400 "context length" errors we halve max_tokens and retry up to 3×.
    effective_max_tokens = min(num_predict, max(1, num_ctx - 512))
    t_start = time.monotonic()
    for _attempt in range(4):
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "seed": seed,
            "max_tokens": effective_max_tokens,
            "stream": False,
            "top_p": 1.0,
            # Mirror llama-server's chat_template_kwargs: explicitly control Qwen3
            # thinking mode so vLLM behaviour matches llama-server for the same model.
            # Models that don't support this field (pre-Qwen3) ignore it silently.
            "chat_template_kwargs": {"enable_thinking": think},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            elapsed_ns = int((time.monotonic() - t_start) * 1e9)
            return _parse_body(body, elapsed_ns)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode()
            if exc.code == 400 and "context length" in err_body and effective_max_tokens > 1:
                effective_max_tokens = max(1, effective_max_tokens // 2)
                continue
            raise OllamaError(f"HTTP {exc.code}: {err_body[:200]}") from exc
        except urllib.error.URLError as exc:
            raise OllamaError(f"URL error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise OllamaError(f"Timed out after {timeout}s") from exc
        except (ConnectionError, OSError) as exc:
            raise OllamaError(f"Connection error (server crash/OOM?): {exc}") from exc
    raise OllamaError(f"max_tokens still exceeds context after 3 halvings (final: {effective_max_tokens})")


def unload_model(base_url: str, model: str, timeout: int = 30) -> None:
    """No-op: lifecycle is managed by VLLMManager.stop()."""
    pass
