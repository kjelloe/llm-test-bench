"""External OpenAI-compatible backend (`--backend openai-ext`): a server the harness does NOT own, on this machine's
GPUs, e.g. Strata's `strata-server`. The harness never starts, stops or loads anything there; whoever started it
declares what runs (`--ext-label`, e.g. "strata 0.1.48 abc1234").

Every request names the one model the server lists in /v1/models (or --ext-model when it lists several). Requests are
greedy (temperature 0, top_p 1, seed) with reasoning set by --think through chat_template_kwargs, like the other
backends. Decode speed comes from a llama.cpp-style `timings` object when the server sends one; otherwise tok/s stays
0 (never completion tokens over request time). Order independence is verified from usage.cached_tokens, as for MLX.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request

from lib.mlx_client import _get_json, _parse_body
from lib.ollama_client import OllamaError, OllamaResponse


def server_info(base_url: str, timeout: int = 10) -> dict:
    """Model listing of a running server; raises OllamaError if it does not answer."""
    listing = _get_json(base_url.rstrip("/") + "/v1/models", timeout)
    return {"models": [m.get("id") for m in listing.get("data") or [] if m.get("id")]}


def served_model(listed: list[str], wanted: str | None) -> str:
    """The model id to put in requests: `wanted` if given (it must be listed), else the only listed one."""
    if wanted:
        if wanted not in listed:
            raise OllamaError(f"--ext-model {wanted!r} is not in the server's /v1/models listing: {listed}")
        return wanted
    if len(listed) != 1:
        raise OllamaError(f"the server lists {len(listed)} models {listed}; name one with --ext-model")
    return listed[0]


def _apply_timings(resp: OllamaResponse, body: dict) -> None:
    timings = body.get("timings") or {}
    per_s = timings.get("predicted_per_second")
    if per_s and per_s > 0 and resp.metrics.eval_count > 0:
        resp.metrics.eval_duration = int(resp.metrics.eval_count / per_s * 1e9)
    elif timings.get("predicted_ms"):
        resp.metrics.eval_duration = int(timings["predicted_ms"] * 1e6)
    if timings.get("prompt_ms"):
        resp.metrics.prompt_eval_duration = int(timings["prompt_ms"] * 1e6)
    if resp.metrics.eval_duration:
        resp.backend_notes.pop("decode_timing", None)


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
        "model": model,
        "messages": messages,
        "max_tokens": num_predict,
        "temperature": temperature,
        "top_p": 1.0,
        "seed": seed,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": think},
    }
    unsupported = ["num_ctx"]   # the server's own context size applies
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
    _apply_timings(resp, body)
    if not think and (resp.thinking or notes.get("content_from_reasoning")):
        notes["reasoning_despite_off"] = True
    return resp


def chat_as(served: str, **kwargs) -> OllamaResponse:
    """chat() with the server's model id in place of the harness's model name."""
    kwargs["model"] = served
    return chat(**kwargs)
