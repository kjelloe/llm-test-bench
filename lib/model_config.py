"""Parse model definition lines from models/*.txt files.

Line format (space-separated fields):
  <ollama-name> [<gguf-file> [<key=val,flag,...>]]

Field 1  ollama model tag — always required
Field 2  GGUF filename relative to LLAMA_MODELS_DIR — required for llama-server
Field 3  comma-separated llama-server startup params
           boolean flags: no_mmap, mlock
           key-value:     n_cpu_moe=35, cache_type_k=turbo4, ngl=999
         Underscores in names become hyphens when turned into CLI flags.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelConfig:
    ollama_name: str
    gguf_file: str | None = None
    params: dict[str, str | bool] = field(default_factory=dict)


def parse_model_line(line: str) -> ModelConfig | None:
    """Parse one line from a models file. Returns None for blank/comment lines."""
    line = line.split("#")[0].strip()
    if not line:
        return None
    parts = line.split()
    ollama_name = parts[0]
    gguf_file = parts[1] if len(parts) > 1 else None
    params: dict[str, str | bool] = {}
    if len(parts) > 2:
        for token in parts[2].split(","):
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                k, v = token.split("=", 1)
                params[k.strip()] = v.strip()
            else:
                params[token] = True
    return ModelConfig(ollama_name=ollama_name, gguf_file=gguf_file, params=params)


def load_model_file(path: str | Path) -> list[ModelConfig]:
    """Parse a models/*.txt file into a list of ModelConfig objects (one per model)."""
    configs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            cfg = parse_model_line(line)
            if cfg is not None:
                configs.append(cfg)
    return configs
