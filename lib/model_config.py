"""Parse model definition lines from models/*.txt and models/*.vllm files.

Line format (space-separated fields):
  <short-name> [<gguf-file> [<key=val,flag,...>]] [hf:<owner/repo>]

Field 1       model name — ollama tag for .txt files; short canonical name for .vllm
Field 2       GGUF filename relative to LLAMA_MODELS_DIR — required for llama-server/vllm
Field 3       comma-separated backend startup params
                llama-server: no_mmap, ngl=999, cache_type_k=f16, ...
                vllm:         tp=2, dtype=auto, max_model_len=32768, enforce_eager, ...
              Underscores in names become hyphens when turned into CLI flags.
hf:<repo>     HuggingFace repo ID for fetch-hf.py; for vllm used as --tokenizer source
              (position-independent after field 1)

Harness-only params (consumed by the harness; not forwarded to the backend):
  thinking      Mark as thinking model (controls system message; .txt and .vllm)
  max_ctx       Hard context cap; harness skips tasks that require more (.txt)
  max_model_len Same as max_ctx for vllm models; controls --max-model-len at startup

Examples:
  gpt-oss:20b
  qwen2.5-coder:14b  model.gguf  hf:Qwen/Qwen2.5-Coder-14B-Instruct-GGUF
  qwen3.5:35b  model.gguf  n_cpu_moe=35,no_mmap  hf:bartowski/Qwen3-235B-A22B-GGUF
  llama3.3:70b  Llama-3.3-70B-Q4_K_S.gguf  tp=2,dtype=auto,max_model_len=32768  hf:meta-llama/Llama-3.3-70B-Instruct
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelConfig:
    ollama_name: str
    gguf_file: str | None = None
    params: dict[str, str | bool] = field(default_factory=dict)
    hf_repo: str | None = None
    max_ctx: int | None = None      # architecture context limit; harness skips tasks requiring more
    is_thinking: bool = False       # True → "After your reasoning, output ONLY..." system message


def parse_model_line(line: str) -> ModelConfig | None:
    """Parse one line from a models file. Returns None for blank/comment lines."""
    line = line.split("#")[0].strip()
    if not line:
        return None
    parts = line.split()
    ollama_name = parts[0]

    # Scan fields after the ollama name: hf: fields are identified by prefix;
    # the remaining positional fields are gguf_file (first) and params (second).
    hf_repo: str | None = None
    positional: list[str] = []
    for part in parts[1:]:
        if part.startswith("hf:"):
            hf_repo = part[3:]
        else:
            positional.append(part)

    gguf_file = positional[0] if positional else None
    params: dict[str, str | bool] = {}
    max_ctx: int | None = None
    is_thinking = False
    if len(positional) > 1:
        for token in positional[1].split(","):
            token = token.strip()
            if not token:
                continue
            if token == "thinking":
                is_thinking = True  # harness-only — not forwarded to llama-server
            elif "=" in token:
                k, v = token.split("=", 1)
                k, v = k.strip(), v.strip()
                if k in ("max_ctx", "max_model_len"):
                    max_ctx = int(v)  # harness-only — max_model_len is the vllm alias
                else:
                    params[k] = v
            else:
                params[token] = True

    return ModelConfig(ollama_name=ollama_name, gguf_file=gguf_file, params=params, hf_repo=hf_repo,
                       max_ctx=max_ctx, is_thinking=is_thinking)


def load_model_file(path: str | Path) -> list[ModelConfig]:
    """Parse a models/*.txt file into a list of ModelConfig objects (one per model)."""
    configs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            cfg = parse_model_line(line)
            if cfg is not None:
                configs.append(cfg)
    return configs
