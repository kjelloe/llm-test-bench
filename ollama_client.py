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
    metrics: OllamaMetrics


class OllamaError(Exception):
    pass


def chat(
    base_url: str,
    model: str,
    messages: list[dict],
    num_ctx: int = 8192,
    temperature: float = 0.0,
    seed: int = 1,
    num_predict: int = 400,
    timeout: int = 120,
) -> OllamaResponse:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
            "seed": seed,
            "num_predict": num_predict,
        },
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
    except urllib.error.HTTPError as exc:
        raise OllamaError(f"HTTP {exc.code}: {exc.read().decode()[:200]}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"URL error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaError(f"Timed out after {timeout}s") from exc

    content = body.get("message", {}).get("content", "")
    return OllamaResponse(
        content=content,
        metrics=OllamaMetrics(
            prompt_eval_count=body.get("prompt_eval_count", 0),
            eval_count=body.get("eval_count", 0),
            prompt_eval_duration=body.get("prompt_eval_duration", 0),
            eval_duration=body.get("eval_duration", 0),
            total_duration=body.get("total_duration", 0),
        ),
    )
