import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class OllamaMetrics:
    prompt_eval_count: int = 0
    eval_count: int = 0
    prompt_eval_duration: int = 0  # nanoseconds
    eval_duration: int = 0         # nanoseconds
    total_duration: int = 0        # nanoseconds

    @property
    def tok_per_s(self) -> float:
        if self.eval_duration > 0:
            return self.eval_count / (self.eval_duration / 1e9)
        return 0.0


@dataclass
class OllamaResponse:
    content: str
    thinking: str          # non-empty for models with thinking mode (deepseek-r1, gemma4, etc.)
    metrics: OllamaMetrics
    finish_reason: str = ""  # "stop" | "length" | "eos" | "" if unavailable


class OllamaError(Exception):
    pass


def unload_model(base_url: str, model: str, timeout: int = 30) -> None:
    """Ask Ollama to evict model weights from VRAM immediately (keep_alive=0). Best-effort."""
    url = base_url.rstrip("/") + "/api/generate"
    payload = {"model": model, "keep_alive": 0}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except Exception:
        pass


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
    thinking_budget: int | None = None,  # unused: Ollama has no thinking budget API
    num_thread: int | None = None,
    keep_alive: str | int | None = None,
) -> OllamaResponse:
    url = base_url.rstrip("/") + "/api/chat"
    options: dict = {
        "num_ctx": num_ctx,
        "temperature": temperature,
        "seed": seed,
        "num_predict": num_predict,
    }
    if num_thread is not None and num_thread > 0:
        options["num_thread"] = num_thread
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,   # False disables reasoning tokens for deepseek-r1, gemma4, etc.
        "options": options,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise OllamaError(f"HTTP {exc.code}: {exc.read().decode()[:200]}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"URL error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaError(f"Timed out after {timeout}s") from exc

    msg = body.get("message", {})
    return OllamaResponse(
        content=msg.get("content", ""),
        thinking=msg.get("thinking", ""),
        finish_reason=body.get("done_reason", ""),
        metrics=OllamaMetrics(
            prompt_eval_count=body.get("prompt_eval_count", 0),
            eval_count=body.get("eval_count", 0),
            prompt_eval_duration=body.get("prompt_eval_duration", 0),
            eval_duration=body.get("eval_duration", 0),
            total_duration=body.get("total_duration", 0),
        ),
    )
