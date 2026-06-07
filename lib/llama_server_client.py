"""llama-server backend: process manager + OpenAI-compatible chat client.

Exposes chat() and unload_model() with the same signatures as ollama_client
so bench.py can select either backend at startup without changing call sites.

One llama-server process per benchmark run. The server is started (or restarted)
by LlamaServerManager.ensure() before each task when the model or ctx-size changes.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from lib.model_config import ModelConfig
from lib.ollama_client import OllamaError, OllamaMetrics, OllamaResponse

# model file uses short/intuitive names; map to actual llama-server CLI flag names
_PARAM_NAME_MAP: dict[str, str] = {
    "ngl": "n-gpu-layers",
}

# flags stored as boolean True in model files but requiring an explicit value in newer
# llama-server builds (e.g. --flash-attn on instead of bare --flash-attn)
_BOOL_EMIT_VALUE: dict[str, str] = {
    "flash-attn": "on",
}

_PORT = 8080
_BASE_URL = f"http://127.0.0.1:{_PORT}"
_HEALTH_URL = f"{_BASE_URL}/health"


def _kill_port_occupant(port: int, timeout: int = 10) -> None:
    """Kill any process already listening on *port* so we can bind it cleanly.

    Uses /proc/net/tcp (Linux-only) to find the PID, then sends SIGTERM followed
    by SIGKILL if the process hasn't exited within *timeout* seconds.
    """
    hex_port = f"{port:04X}"
    try:
        tcp_data = Path("/proc/net/tcp").read_text()
    except OSError:
        return  # not Linux — skip
    pid: int | None = None
    for line in tcp_data.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        local_addr = parts[1]
        inode = parts[9]
        if local_addr.endswith(f":{hex_port}"):
            # find the PID that owns this inode via /proc/<pid>/fd symlinks
            inode_target = f"socket:[{inode}]"
            try:
                for fd_path in Path("/proc").glob("*/fd/*"):
                    try:
                        if os.readlink(str(fd_path)) == inode_target:
                            pid = int(fd_path.parts[2])
                            break
                    except (OSError, ValueError):
                        continue
            except Exception:
                pass
            break
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)  # probe: raises if process is gone
            except ProcessLookupError:
                return
            time.sleep(0.5)
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class LlamaServerManager:
    """Manages a single llama-server subprocess for the duration of a benchmark run."""

    def __init__(self, models_dir: str, bin_path: str = "llama-server",
                 debug: bool = False) -> None:
        self.models_dir = Path(models_dir)
        self.bin_path = bin_path
        self.debug = debug
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
        """Start or restart the server if model changed or ctx grew. No-op if already suitable."""
        if not self.needs_restart(cfg, ctx_size):
            return
        self.stop()
        self._start(cfg, ctx_size, num_threads=num_threads, startup_timeout=startup_timeout)

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
        if not self.debug and self._proc.stderr:
            try:
                self._proc.stderr.close()
            except Exception:
                pass
        self._proc = None
        self._current_model = None
        self._current_ctx = 0

    def _start(self, cfg: ModelConfig, ctx_size: int,
               num_threads: int | None = None, startup_timeout: int = 600) -> None:
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
        ]
        if num_threads and num_threads > 0:
            cmd.extend(["--threads", str(num_threads)])
        for key, val in cfg.params.items():
            cli_key = _PARAM_NAME_MAP.get(key, key.replace("_", "-"))
            flag = "--" + cli_key
            if val is True:
                if cli_key in _BOOL_EMIT_VALUE:
                    cmd.extend([flag, _BOOL_EMIT_VALUE[cli_key]])
                else:
                    cmd.append(flag)
            else:
                # | is used as sub-separator for comma-containing values (e.g. tensor_split=1|1)
                cmd.extend([flag, str(val).replace("|", ",")])

        # Evict any stale llama-server (or other process) already on our port.
        # Without this, _wait_ready() may get a health-OK from the wrong server.
        _kill_port_occupant(_PORT)

        # debug=True: inherit terminal so output streams live; useful for startup diagnosis.
        # debug=False: capture stderr so it can be shown on crash/timeout.
        stderr = None if self.debug else subprocess.PIPE
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=stderr)
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
                msg = "llama-server exited unexpectedly during startup"
                if not self.debug and self._proc.stderr:
                    try:
                        stderr_out = self._proc.stderr.read().decode(errors="replace").strip()
                        if stderr_out:
                            msg += f"\n--- stderr ---\n{stderr_out[-2000:]}"
                    except Exception:
                        pass
                raise RuntimeError(msg)
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


def _parse_body(body: dict, elapsed_ns: int) -> OllamaResponse:
    """Parse an OpenAI-compatible /v1/chat/completions response dict."""
    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content       = msg.get("content")           or ""
    thinking      = msg.get("reasoning_content") or ""
    finish_reason = choice.get("finish_reason")  or ""
    # Thinking models on llama-server return reasoning in reasoning_content and
    # the actual answer in content. When the model exhausts its token budget
    # inside the reasoning phase, content arrives empty. Fall back so that
    # BEGIN_FILE blocks produced during reasoning are not silently discarded.
    if not content and thinking:
        content  = thinking
        thinking = ""

    usage = body.get("usage") or {}
    prompt_tokens      = usage.get("prompt_tokens", 0)
    completion_tokens  = usage.get("completion_tokens", 0)

    timings      = body.get("timings") or {}
    predicted_ms = timings.get("predicted_ms")
    prompt_ms    = timings.get("prompt_ms")
    if predicted_ms is not None and predicted_ms > 0:
        eval_duration_ns        = int(predicted_ms * 1e6)
        prompt_eval_duration_ns = int((prompt_ms or 0) * 1e6)
    else:
        eval_duration_ns        = elapsed_ns
        prompt_eval_duration_ns = 0

    return OllamaResponse(
        content=content,
        thinking=thinking,
        finish_reason=finish_reason,
        metrics=OllamaMetrics(
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            prompt_eval_duration=prompt_eval_duration_ns,
            eval_duration=eval_duration_ns,
            total_duration=elapsed_ns,
        ),
    )


def chat(
    base_url: str,
    model: str,                   # unused: llama-server is single-model per process
    messages: list[dict],
    num_ctx: int = 8192,          # unused: set at server startup via LlamaServerManager
    temperature: float = 0.0,
    seed: int = 1,
    num_predict: int = 400,
    timeout: int = 300,
    think: bool = False,          # Qwen3: enables thinking via chat_template_kwargs (requires GGUF with enable_thinking in template)
    thinking_budget: int | None = None,  # Qwen3: cap thinking tokens; None = unlimited
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
        # Explicit deterministic sampling — do not rely on llama-server defaults
        # matching Ollama's defaults (they differ in top_k and repeat_penalty).
        "top_p": 1.0,
        "top_k": 1,
        "repeat_penalty": 1.0,
    }
    # Always send enable_thinking explicitly so Qwen3 GGUFs (which default to thinking-enabled)
    # are deterministically controlled. think=False → disable; think=True → enable.
    # Other models ignore unknown template variables.
    # Note: assistant prefill is INCOMPATIBLE with enable_thinking — never combine them.
    kwargs: dict = {"enable_thinking": think}
    if think and thinking_budget is not None:
        kwargs["thinking_budget"] = thinking_budget
    payload["chat_template_kwargs"] = kwargs
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
    """No-op: lifecycle is managed by LlamaServerManager.stop()."""
    pass
