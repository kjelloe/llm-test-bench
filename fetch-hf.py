#!/usr/bin/env python3
"""Download GGUF files from HuggingFace Hub.

Reads models/*.txt files, finds models with hf: repo fields, and downloads
missing GGUF files to $LLAMA_MODELS_DIR using huggingface_hub.

Usage:
  ./fetch-hf.sh                          # scan all models/*.txt
  ./fetch-hf.sh models/default.txt       # specific file(s)
  ./fetch-hf.sh --models qwen3.5:35b     # specific model(s) only
  ./fetch-hf.sh --dry-run                # show what would be downloaded
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.model_config import ModelConfig, load_model_file

_SHARD_RE = re.compile(r'(-\d{5})-of-(\d{5})\.gguf$', re.IGNORECASE)


def _all_shard_names(gguf_file: str) -> list[str]:
    """For a shard-1 file, return all N shard filenames. For single files, return [gguf_file]."""
    m = _SHARD_RE.search(gguf_file)
    if not m:
        return [gguf_file]
    shard_num = int(m.group(1).lstrip('-'))
    total = int(m.group(2))
    if shard_num != 1 or total == 1:
        return [gguf_file]
    base = gguf_file[:m.start()]
    return [f"{base}-{i:05d}-of-{total:05d}.gguf" for i in range(1, total + 1)]


def _all_shards_present(cfg: ModelConfig, dest_dir: Path) -> bool:
    return all((dest_dir / name).exists() for name in _all_shard_names(cfg.gguf_file))


def _resolve_model_files(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(p) for p in paths]
    models_dir = Path(__file__).parent / "models"
    return sorted(models_dir.glob("*.txt"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download GGUF files from HuggingFace Hub to $LLAMA_MODELS_DIR"
    )
    parser.add_argument(
        "model_files", nargs="*", metavar="FILE",
        help="models/*.txt files to read (default: all models/*.txt files)",
    )
    parser.add_argument(
        "--models", nargs="+", metavar="MODEL",
        help="Only download specific models by Ollama name (e.g. qwen3.5:35b)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be downloaded without downloading anything",
    )
    args = parser.parse_args()

    models_dir = os.environ.get("LLAMA_MODELS_DIR", "")
    if not models_dir:
        print("Error: LLAMA_MODELS_DIR environment variable is not set.", file=sys.stderr)
        print("Set it to the directory where GGUF files should be stored.", file=sys.stderr)
        sys.exit(1)
    dest_dir = Path(models_dir)
    if not dest_dir.exists():
        print(f"Error: LLAMA_MODELS_DIR does not exist: {dest_dir}", file=sys.stderr)
        sys.exit(1)

    files = _resolve_model_files(args.model_files)
    if not files:
        print("No model files found.", file=sys.stderr)
        sys.exit(1)

    # Collect all downloadable configs across all files (dedup by ollama_name)
    seen: set[str] = set()
    configs: list[ModelConfig] = []
    for f in files:
        if not f.exists():
            print(f"Warning: file not found, skipping: {f}", file=sys.stderr)
            continue
        for cfg in load_model_file(f):
            if cfg.ollama_name in seen:
                continue
            seen.add(cfg.ollama_name)
            if not cfg.hf_repo or not cfg.gguf_file:
                continue
            if args.models and cfg.ollama_name not in args.models:
                continue
            configs.append(cfg)

    if not configs:
        print("No models with hf: repo fields found in the specified files.")
        print("Add  hf:<owner/repo>  to a model line to enable downloading, e.g.:")
        print("  qwen2.5-coder:14b  model.gguf  hf:Qwen/Qwen2.5-Coder-14B-Instruct-GGUF")
        return

    already_present = [c for c in configs if _all_shards_present(c, dest_dir)]
    to_download = [c for c in configs if not _all_shards_present(c, dest_dir)]

    if already_present:
        print(f"Already present ({len(already_present)}):")
        for cfg in already_present:
            shards = _all_shard_names(cfg.gguf_file)
            total_mb = sum((dest_dir / s).stat().st_size for s in shards) / 1024 / 1024
            parts_note = f"  ({len(shards)} parts)" if len(shards) > 1 else ""
            print(f"  ✓  {cfg.gguf_file}{parts_note}  ({total_mb:,.0f} MB)  [{cfg.ollama_name}]")
        print()

    if not to_download:
        print("Nothing to download.")
        return

    print(f"{'Would download' if args.dry_run else 'Downloading'} ({len(to_download)}):")
    for cfg in to_download:
        shards = _all_shard_names(cfg.gguf_file)
        parts_note = f"  ({len(shards)} parts)" if len(shards) > 1 else ""
        print(f"  {cfg.ollama_name}")
        print(f"    repo : {cfg.hf_repo}")
        print(f"    file : {cfg.gguf_file}{parts_note}")
        print(f"    dest : {dest_dir / cfg.gguf_file}{parts_note}")

    if args.dry_run:
        return

    print()
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print(
            "Error: huggingface_hub is not installed.\n"
            "Run:  pip install huggingface_hub",
            file=sys.stderr,
        )
        sys.exit(1)

    failed: list[tuple[ModelConfig, str]] = []
    for cfg in to_download:
        shards = _all_shard_names(cfg.gguf_file)
        print(f"[{cfg.ollama_name}]  {cfg.hf_repo} / {cfg.gguf_file}"
              + (f"  (+{len(shards)-1} more parts)" if len(shards) > 1 else ""))
        try:
            for shard_name in shards:
                local_path = hf_hub_download(
                    repo_id=cfg.hf_repo,
                    filename=shard_name,
                    local_dir=str(dest_dir),
                )
                size_mb = Path(local_path).stat().st_size / 1024 / 1024
                print(f"  → {local_path}  ({size_mb:,.0f} MB)")
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failed.append((cfg, str(exc)))

    print()
    if failed:
        print(f"{len(failed)} download(s) failed:")
        for cfg, err in failed:
            print(f"  {cfg.ollama_name}: {err}")
        sys.exit(1)
    else:
        print(f"All {len(to_download)} download(s) complete.")


if __name__ == "__main__":
    main()
