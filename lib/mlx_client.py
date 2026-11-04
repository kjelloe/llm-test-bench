"""MLX backend (Apple Silicon): a client for an mlx-lm server (`mlx_lm.server`) that is already running, often on
another machine (a Mac does the inference, this harness prepares and grades the tasks).

The harness owns nothing on that server: it never starts, stops, unloads or loads a model there. Every request asks for
"default_model", the model the server was started with, because a request naming any other model makes mlx-lm load it
(downloading it from Hugging Face if needed). Which model that is, is declared in the .mlx model file and checked
against the server's /v1/models listing; mlx-lm offers no stronger check.

Request fields follow mlx-lm 0.32's server (`max_tokens`, `seed`, `chat_template_kwargs`, ...), not llama-server's.
A request with a seed is served on mlx-lm's sequential path, never batched with another.

What mlx-lm does not report stays unreported: it has no prefill/decode timings, so the metrics carry the end-to-end
time only and tok_per_s stays 0 (never completion tokens over request time). Context size and CPU threads are not
request controls there; requested ones are listed as unsupported in the record's backend_notes.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request

from lib.ollama_client import OllamaError, OllamaMetrics, OllamaResponse

SERVED_MODEL = "default_model"


def _get_json(url: str, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise OllamaError(f"HTTP {exc.code} from {url}: {exc.read().decode(errors='replace')[:200]}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"cannot reach the MLX server at {url}: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OllamaError(f"timed out after {timeout}s: {url}") from exc
    except json.JSONDecodeError as exc:
        raise OllamaError(f"malformed JSON from {url}: {exc}") from exc


def server_info(base_url: str, timeout: int = 10) -> dict:
    """Health and model listing of a running mlx-lm server; raises OllamaError if it does not answer."""
    base = base_url.rstrip("/")
    health = _get_json(base + "/health", timeout)
    listing = _get_json(base + "/v1/models", timeout)
    return {"health": health.get("status"), "models": [m.get("id") for m in listing.get("data") or []]}


def model_listed(declared: str, listed: list[str]) -> bool:
    """True when the declared model (HF repo id, or a local directory on the server) is in the server's listing.
    mlx-lm lists every MLX model in its HF cache plus the resolved --model path, so this proves presence, not use."""
    d = declared.rstrip("/")
    return any(m == d or m.rstrip("/").endswith("/" + d.lstrip("./")) for m in listed if m)


def _parse_body(body: object, elapsed_ns: int, notes: dict) -> OllamaResponse:
    if not isinstance(body, dict) or not isinstance(body.get("choices"), list) or not body["choices"]:
        raise OllamaError(f"malformed response (no choices): {json.dumps(body)[:200]}")
    choice = body["choices"][0]
    msg = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(msg, dict):
        raise OllamaError(f"malformed response (no message): {json.dumps(choice)[:200]}")
    content = msg.get("content") or ""
    thinking = msg.get("reasoning") or ""
    if not content and thinking:
        # same rule as the llama-server and vLLM clients: a reasoning-only answer is parsed as the answer
        content, thinking = thinking, ""
        notes["content_from_reasoning"] = True

    usage = body.get("usage")
    if isinstance(usage, dict):
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        if cached is not None:
            notes["cached_prompt_tokens"] = int(cached)
    else:
        prompt_tokens = completion_tokens = 0
        notes["usage"] = "missing"

    return OllamaResponse(
        content=content,
        thinking=thinking,
        finish_reason=choice.get("finish_reason") or "",
        metrics=OllamaMetrics(
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            prompt_eval_duration=0,
            eval_duration=0,           # unavailable: no decode timing from mlx-lm
            total_duration=elapsed_ns,
        ),
        backend_notes=notes,
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
    payload = {
        "model": SERVED_MODEL,
        "messages": messages,
        "max_tokens": num_predict,
        "temperature": temperature,
        "top_p": 1.0,
        "seed": seed,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": think},
    }
    unsupported = ["num_ctx"]   # mlx-lm has no per-request context size; the model's own limit applies
    if num_thread:
        unsupported.append("num_thread")
    if thinking_budget:
        unsupported.append("thinking_budget")
    notes: dict = {
        "effective": {k: payload[k] for k in ("max_tokens", "temperature", "top_p", "seed")}
                     | {"enable_thinking": think},
        "unsupported": unsupported,
        "decode_timing": "unavailable",
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t_start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise OllamaError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:200]}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise OllamaError(f"Timed out after {timeout}s") from exc
        raise OllamaError(f"URL error: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OllamaError(f"Timed out after {timeout}s") from exc
    except (ConnectionError, OSError) as exc:
        raise OllamaError(f"Connection error (server crash/OOM?): {exc}") from exc
    elapsed_ns = int((time.monotonic() - t_start) * 1e9)
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaError(f"malformed JSON response: {raw[:200]!r}") from exc
    resp = _parse_body(body, elapsed_ns, notes)
    if not think and (resp.thinking or notes.get("content_from_reasoning")):
        notes["reasoning_despite_off"] = True   # the chat template ignored enable_thinking=false
    return resp


def unload_model(base_url: str, model: str, timeout: int = 30) -> None:
    """No-op: the harness does not own the MLX server."""
