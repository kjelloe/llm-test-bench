#!/usr/bin/env python3
"""Search HuggingFace Hub for GGUF model files.

Two modes:

  ./search-hf.sh                        -- scan models/*.txt, search for every model
                                           that has no GGUF entry yet
  ./search-hf.sh "qwen2.5 coder 14b"   -- direct search by query

Auth: pass --token, set HF_TOKEN env var, or run 'huggingface-cli login' once.
Without a token the Hub rate-limits aggressively; a free account token is enough.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_PREFERRED_QUANTS = ["Q4_K_M", "Q5_K_M", "Q4_K_S", "Q4_K", "Q8_0", "Q6_K"]
_MAX_REPOS = 5
_MAX_FILES_SHOWN = 8
_MIN_FILE_BYTES = 100 * 1024 * 1024  # skip files < 100 MB (e.g. tiny header shards)

# Keywords that suggest a fine-tune / abliterated / uncensored variant rather than
# the base instruct model.  We annotate these repos but still show them.
_FINETUNE_KEYWORDS = {"uncensored", "abliterated", "jailbreak", "aggressive", "finetune"}

_SHARD_RE = re.compile(r'(-\d{5})-of-(\d{5})\.gguf$', re.IGNORECASE)


# ── shard helpers ─────────────────────────────────────────────────────────────

def _parse_shard(filename: str) -> tuple[str, int, int] | None:
    """Returns (base, shard_num, total_shards) or None if not a shard file."""
    m = _SHARD_RE.search(filename)
    if not m:
        return None
    return (
        filename[:m.start()],          # base path (no shard suffix, no .gguf)
        int(m.group(1).lstrip('-')),   # this shard's number (1-based)
        int(m.group(2)),               # total shards
    )


# ── formatting helpers ────────────────────────────────────────────────────────

def _fmt_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "  ?  "
    gb = size_bytes / 1024 ** 3
    return f"{gb:5.1f} GB" if gb >= 1 else f"{size_bytes / 1024 ** 2:5.0f} MB"


def _fmt_downloads(n: int | None) -> str:
    if n is None:
        return ""
    if n >= 1_000_000:
        return f"↓ {n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"↓ {n / 1_000:.0f}K"
    return f"↓ {n}"


def _suggest_file(files: list[dict]) -> dict | None:
    """Best file: Q4_K_M preferred; single-file over shard; skip tiny (<100 MB) files.

    For sharded models use total group size for the size threshold so that repos
    with a tiny header shard-1 (e.g. 12 MB) are still included — shard-1 must be
    returned so fetch-hf.py can enumerate all parts correctly.
    """
    # Pre-compute total size per shard group and find shard-1 file objects.
    shard_group_bytes: dict[str, int] = {}
    shard_group_first: dict[str, dict] = {}
    for f in files:
        info = _parse_shard(f["name"])
        if info:
            base, num, _ = info
            shard_group_bytes[base] = shard_group_bytes.get(base, 0) + (f.get("size") or 0)
            if num == 1:
                shard_group_first[base] = f

    singles = []
    shard_firsts = []
    for f in files:
        info = _parse_shard(f["name"])
        if info is None:
            if (f.get("size") or 0) >= _MIN_FILE_BYTES:
                singles.append(f)
        elif info[1] == 1:
            base = info[0]
            if shard_group_bytes.get(base, 0) >= _MIN_FILE_BYTES:
                shard_firsts.append(f)

    for candidate_set in (singles, shard_firsts):
        for quant in _PREFERRED_QUANTS:
            for f in candidate_set:
                if quant.lower() in f["name"].lower():
                    return f

    # Fall back: first qualifying single or shard-1
    for f in (singles or shard_firsts):
        return f
    # Last resort: shard-1 from any large-enough group
    for base, total in shard_group_bytes.items():
        if total >= _MIN_FILE_BYTES and base in shard_group_first:
            return shard_group_first[base]
    return None


def _ollama_to_query(ollama_name: str) -> str:
    """'qwen2.5-coder:14b' → 'qwen2.5-coder 14b'"""
    return ollama_name.replace(":", " ")


# ── HF API calls ──────────────────────────────────────────────────────────────

def _search_repos(api, query: str, limit: int, author: str | None = None) -> list:
    # Fetch more than needed so sorting by downloads locally gives better results.
    # filter="gguf" restricts to repos tagged with the gguf library.
    kwargs: dict = {"search": query, "filter": "gguf", "limit": max(limit * 4, 20)}
    if author:
        kwargs["author"] = author
    results = list(api.list_models(**kwargs))
    results.sort(key=lambda m: getattr(m, "downloads", 0) or 0, reverse=True)
    return results[:limit]


def _get_gguf_files(api, repo_id: str) -> list[dict]:
    """Return [{name, size}] for every .gguf file in the repo."""
    try:
        info = api.model_info(repo_id, files_metadata=True)
        return [
            {"name": s.rfilename, "size": s.size}
            for s in (info.siblings or [])
            if s.rfilename.endswith(".gguf")
        ]
    except Exception:
        return []


# ── display ───────────────────────────────────────────────────────────────────

def _print_repo_results(
    repo,
    files: list[dict],
    already_downloaded: set[str],
    suggested: dict | None,
    ollama_name: str | None,
    max_files: int = _MAX_FILES_SHOWN,
) -> str | None:
    """Print one repo block and return the models/*.txt suggestion line, or None."""
    dl = _fmt_downloads(getattr(repo, "downloads", None))
    # Annotate fine-tune / uncensored variants so they stand out.
    repo_words = set(re.split(r'[\-_/]', repo.id.lower()))
    finetune_note = "  ⚠ fine-tune variant" if repo_words & _FINETUNE_KEYWORDS else ""
    print(f"  {repo.id}  {dl}{finetune_note}")
    if not files:
        print("    (no .gguf files found)")
        return None

    # Pre-compute total sizes across all shards so we can display a meaningful size.
    shard_total_bytes: dict[str, int] = {}
    shard_total_count: dict[str, int] = {}
    for f in files:
        info = _parse_shard(f["name"])
        if info:
            base, _, total = info
            shard_total_bytes[base] = shard_total_bytes.get(base, 0) + (f.get("size") or 0)
            shard_total_count[base] = total

    # Build display list: skip non-first shards (collapse each group to one row).
    display: list[dict] = []
    seen_bases: set[str] = set()
    for f in files:
        info = _parse_shard(f["name"])
        if info:
            base, num, _ = info
            if num == 1 and base not in seen_bases:
                seen_bases.add(base)
                display.append(f)
        else:
            display.append(f)

    # Ensure the ★ suggested entry is always in the visible window.
    visible = display[:max_files]
    hidden_count = len(display) - max_files
    if suggested and suggested not in visible:
        visible = display[:max_files - 1] + [suggested]
        hidden_count = max(0, len(display) - max_files)

    for f in visible:
        star = " ★" if f is suggested else "  "
        dl_mark = " ✓" if f["name"] in already_downloaded else ""
        info = _parse_shard(f["name"])
        if info:
            base, _, total = info
            size_str = _fmt_size(shard_total_bytes.get(base))
            parts_note = f"  ({total} parts)" if total > 1 else ""
            print(f"    {star} {size_str}  {f['name']}{parts_note}{dl_mark}")
        else:
            print(f"    {star} {_fmt_size(f['size'])}  {f['name']}{dl_mark}")

    if hidden_count > 0:
        print(f"       … {hidden_count} more file(s)")

    if not suggested:
        return None

    info = _parse_shard(suggested["name"])
    shard_note = f"  # {info[2]}-part model — fetch-hf.sh downloads all parts" if info else ""
    if ollama_name:
        line = f"{ollama_name}  {suggested['name']}  hf:{repo.id}"
    else:
        line = f"<ollama-name>  {suggested['name']}  hf:{repo.id}"
    print(f"\n  → models/*.txt:  {line}{shard_note}")
    return line + shard_note


def _run_search(api, query: str, ollama_name: str | None,
                already_downloaded: set[str], limit: int,
                max_files: int = _MAX_FILES_SHOWN,
                author: str | None = None) -> list[str]:
    """Print search results and return all models/*.txt suggestion lines."""
    label = ollama_name or f'"{query}"'
    print(f"\n{'━' * 70}")
    author_note = f"  author:{author}" if author else ""
    print(f"  {label}  (query: {query!r}{author_note})")
    print(f"{'━' * 70}")

    repos = _search_repos(api, query, limit, author=author)
    if not repos:
        print("  No GGUF repos found.")
        return []

    suggestions: list[str] = []
    printed = 0
    for repo in repos:
        files = _get_gguf_files(api, repo.id)
        if not files:
            continue
        suggested = _suggest_file(files)
        line = _print_repo_results(repo, files, already_downloaded, suggested, ollama_name, max_files=max_files)
        if line:
            suggestions.append(line)
        printed += 1
        if printed >= limit:
            break
        print()

    if printed == 0:
        print("  No repos with .gguf files found.")
    return suggestions


# ── summary ───────────────────────────────────────────────────────────────────

def _print_summary(suggestions: list[str]) -> None:
    if not suggestions:
        return
    print(f"\n{'━' * 70}")
    print("  SUMMARY — paste into models/*.txt")
    print(f"{'━' * 70}")
    for line in suggestions:
        print(f"  {line}")
    print()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search HuggingFace Hub for GGUF model files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ./search-hf.sh                       # search for unconfigured models in models/*.txt\n"
            "  ./search-hf.sh 'qwen2.5 coder 14b'  # direct query\n"
            "  ./search-hf.sh --limit 3             # fewer results per model\n"
        ),
    )
    parser.add_argument(
        "query", nargs="?", default=None,
        help="Search query (default: scan models/*.txt for unconfigured models)",
    )
    parser.add_argument(
        "--token", default=os.environ.get("HF_TOKEN"),
        help="HuggingFace API token (default: HF_TOKEN env var or ~/.cache/huggingface/token)",
    )
    parser.add_argument(
        "--limit", type=int, default=_MAX_REPOS,
        help=f"Max repos to show per model (default: {_MAX_REPOS})",
    )
    parser.add_argument(
        "--max-files", type=int, default=_MAX_FILES_SHOWN,
        help=f"Max files to list per repo (default: {_MAX_FILES_SHOWN}; use 0 for all)",
    )
    parser.add_argument(
        "--top-only", action="store_true",
        help="In the summary, show only the top-ranked suggestion per model (not one per repo)",
    )
    parser.add_argument(
        "--author",
        help="Filter results to a specific HuggingFace author/org (e.g. bartowski, unsloth)",
    )
    parser.add_argument(
        "--model-files", nargs="*", metavar="FILE",
        help="models/*.txt files to scan (default: all models/*.txt; ignored when query given)",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print(
            "Error: huggingface_hub is not installed.\n"
            "Use the wrapper:  ./search-hf.sh  (activates the project venv automatically)\n"
            "Or install manually:  source .venv/bin/activate && pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    api = HfApi(token=args.token or None)

    max_files = args.max_files if args.max_files > 0 else 9999

    # Figure out which files are already downloaded (optional, for ✓ markers)
    already_downloaded: set[str] = set()
    models_dir = os.environ.get("LLAMA_MODELS_DIR", "")
    if models_dir and Path(models_dir).exists():
        already_downloaded = {p.name for p in Path(models_dir).glob("*.gguf")}

    # ── Direct query mode ─────────────────────────────────────────────────────
    if args.query:
        suggestions = _run_search(api, args.query, ollama_name=None,
                                   already_downloaded=already_downloaded,
                                   limit=args.limit, max_files=max_files,
                                   author=args.author)
        _print_summary(suggestions[:1] if args.top_only else suggestions)
        return

    # ── From-models mode ──────────────────────────────────────────────────────
    from lib.model_config import load_model_file

    script_dir = Path(__file__).parent
    if args.model_files:
        files = [Path(f) for f in args.model_files]
    else:
        files = sorted((script_dir / "models").glob("*.txt"))

    if not files:
        print("No model files found.", file=sys.stderr)
        sys.exit(1)

    # Collect models missing a GGUF entry (dedup by ollama_name)
    seen: set[str] = set()
    unconfigured: list[str] = []
    configured: list[str] = []
    for f in files:
        if not f.exists():
            continue
        for cfg in load_model_file(f):
            if cfg.ollama_name in seen:
                continue
            seen.add(cfg.ollama_name)
            if cfg.gguf_file:
                configured.append(cfg.ollama_name)
            else:
                unconfigured.append(cfg.ollama_name)

    if configured:
        print(f"Already configured ({len(configured)}): " + "  ".join(configured))
    if not unconfigured:
        print("All models in models/*.txt already have GGUF entries.")
        return

    all_suggestions: list[str] = []
    print(f"\nSearching for {len(unconfigured)} unconfigured model(s) …")
    for name in unconfigured:
        results = _run_search(api, _ollama_to_query(name), ollama_name=name,
                              already_downloaded=already_downloaded,
                              limit=args.limit, max_files=max_files,
                              author=args.author)
        all_suggestions += results[:1] if args.top_only else results
    _print_summary(all_suggestions)


if __name__ == "__main__":
    main()
