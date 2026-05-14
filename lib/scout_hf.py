#!/usr/bin/env python3
"""Scout HuggingFace Hub for new GGUF models useful for coding + context benchmarks.

Saves a state snapshot to output/hf-scout-state.json and diffs against the
previous snapshot on subsequent runs — showing new repos, updated file lists,
and repos that disappeared.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Queries covering coding/instruction model families suitable for 24 GB VRAM.
# Each is run against the HF GGUF library tag and results are deduped by repo_id.
SCOUT_QUERIES: list[str] = [
    "qwen3 coder instruct",
    "qwen3 instruct moe",
    "qwen2.5 coder instruct",
    "devstral coding",
    "deepseek coder instruct",
    "llama3 coding instruct",
    "gemma instruct",
    "gpt-oss",
    "codestral",
    "phi4 coding instruct",
]

_REPOS_PER_QUERY = 8
_PREFERRED_QUANTS = ["Q4_K_M", "Q5_K_M", "Q4_K_S", "Q4_K", "Q8_0", "Q6_K"]
_MIN_FILE_BYTES = 100 * 1024 * 1024   # skip files < 100 MB (tiny header shards etc.)
_VRAM_BUDGET_GB = 20.0                 # files > this flagged as "tight" on a 24 GB card
_SHARD_RE = re.compile(r'(-\d{5})-of-(\d{5})\.gguf$', re.IGNORECASE)
_QUANT_RE = re.compile(r'\b(IQ\d[_A-Z0-9]*|Q\d[_A-Z0-9]*|F16|BF16|MXFP4|FP8)\b', re.IGNORECASE)


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fmt_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "?  "
    gb = size_bytes / 1024 ** 3
    return f"{gb:.1f} GB" if gb >= 1 else f"{size_bytes / 1024 ** 2:.0f} MB"


def _fmt_dl(n: int | None) -> str:
    if not n:
        return ""
    if n >= 1_000_000:
        return f"↓{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"↓{n / 1_000:.0f}K"
    return f"↓{n}"


def _extract_quant(filename: str) -> str | None:
    m = _QUANT_RE.search(Path(filename).name)
    return m.group(0).upper() if m else None


def _parse_shard(filename: str) -> tuple[str, int, int] | None:
    m = _SHARD_RE.search(filename)
    if not m:
        return None
    return filename[:m.start()], int(m.group(1).lstrip('-')), int(m.group(2))


def _vram_label(size_bytes: int | None) -> str:
    if size_bytes is None:
        return ""
    gb = size_bytes / 1024 ** 3
    if gb <= _VRAM_BUDGET_GB:
        return "✓"
    if gb <= 24.0:
        return "~"   # tight — limited KV cache headroom
    return "✗"       # needs multi-GPU or heavy CPU offload


# ── GGUF file helpers ─────────────────────────────────────────────────────────

def _get_gguf_files(api, repo_id: str) -> list[dict]:
    try:
        info = api.model_info(repo_id, files_metadata=True)
        return [
            {"name": s.rfilename, "size": s.size, "quant": _extract_quant(s.rfilename)}
            for s in (info.siblings or [])
            if s.rfilename.endswith(".gguf")
        ]
    except Exception:
        return []


def _suggest_file(files: list[dict]) -> dict | None:
    """Return the best single GGUF file (Q4_K_M preferred, ≥ 100 MB)."""
    shard_total: dict[str, int] = {}
    shard_first: dict[str, dict] = {}
    for f in files:
        info = _parse_shard(f["name"])
        if info:
            base, num, _ = info
            shard_total[base] = shard_total.get(base, 0) + (f.get("size") or 0)
            if num == 1:
                shard_first[base] = f

    singles = [f for f in files
               if not _parse_shard(f["name"]) and (f.get("size") or 0) >= _MIN_FILE_BYTES]
    shards = [shard_first[b] for b, t in shard_total.items()
              if t >= _MIN_FILE_BYTES and b in shard_first]

    for pool in (singles, shards):
        for q in _PREFERRED_QUANTS:
            for f in pool:
                if (f.get("quant") or "").upper() == q:
                    return f
    return next(iter(singles or shards), None)


def _suggested_size(rec: dict) -> int | None:
    sug = rec.get("suggested_file")
    if not sug:
        return None
    return next((f["size"] for f in rec["files"] if f["name"] == sug), None)


# ── HF search ─────────────────────────────────────────────────────────────────

def _search_repos(api, query: str, limit: int) -> list:
    results = list(api.list_models(search=query, filter="gguf", limit=max(limit * 4, 20)))
    results.sort(key=lambda m: getattr(m, "downloads", 0) or 0, reverse=True)
    return results[:limit]


def _scout(api, queries: list[str], repos_per_query: int) -> dict[str, dict]:
    """Run all queries; return {repo_id: repo_record} deduplicated."""
    found: dict[str, dict] = {}
    for query in queries:
        print(f"  {query!r:40s} … ", end="", flush=True)
        try:
            repos = _search_repos(api, query, repos_per_query)
        except Exception as exc:
            print(f"ERROR ({exc})")
            continue
        added = 0
        for repo in repos:
            rid = repo.id
            if rid in found:
                found[rid]["source_queries"].append(query)
                continue
            files = _get_gguf_files(api, rid)
            if not files:
                continue
            suggested = _suggest_file(files)
            found[rid] = {
                "downloads": getattr(repo, "downloads", None),
                "likes": getattr(repo, "likes", None),
                "files": files,
                "suggested_file": suggested["name"] if suggested else None,
                "source_queries": [query],
            }
            added += 1
        print(f"{len(repos)} repos  (+{added} new)")
    return found


# ── State I/O ─────────────────────────────────────────────────────────────────

def _load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Diff ──────────────────────────────────────────────────────────────────────

def _file_set(rec: dict) -> set[str]:
    return {f["name"] for f in rec.get("files", [])}


def _compute_diff(
    old_repos: dict, new_repos: dict
) -> tuple[list[tuple], list[tuple], list[str]]:
    """Returns (new_entries, updated_entries, gone_entries)."""
    new_entries: list[tuple[str, dict]] = []
    updated_entries: list[tuple[str, dict, list[str], list[str]]] = []
    gone_entries: list[str] = []

    for rid, rec in new_repos.items():
        if rid not in old_repos:
            new_entries.append((rid, rec))
        else:
            old_files = _file_set(old_repos[rid])
            new_files = _file_set(rec)
            added = sorted(new_files - old_files)
            removed = sorted(old_files - new_files)
            if added or removed:
                updated_entries.append((rid, rec, added, removed))

    for rid in old_repos:
        if rid not in new_repos:
            gone_entries.append(rid)

    return new_entries, updated_entries, gone_entries


# ── Display ───────────────────────────────────────────────────────────────────

def _print_repo_line(rid: str, rec: dict, indent: str = "    ") -> None:
    dl = _fmt_dl(rec.get("downloads"))
    sug = rec.get("suggested_file", "")
    size = _suggested_size(rec)
    vram = _vram_label(size)
    size_str = _fmt_size(size) if size else ""
    dl_str = f"  {dl}" if dl else ""
    vram_str = f"  {size_str} {vram}" if size_str else ""
    print(f"{indent}{rid}{dl_str}{vram_str}")
    if sug:
        print(f"{indent}  → {sug}")


def _print_diff(new_e: list, upd_e: list, gone_e: list) -> None:
    if new_e:
        print(f"\n  NEW ({len(new_e)}):")
        by_dl = sorted(new_e, key=lambda x: x[1].get("downloads") or 0, reverse=True)
        for rid, rec in by_dl:
            _print_repo_line(rid, rec)

    if upd_e:
        print(f"\n  UPDATED ({len(upd_e)})  — file list changed:")
        for rid, rec, added, removed in upd_e:
            print(f"    {rid}")
            for name in added:
                size = next((f["size"] for f in rec["files"] if f["name"] == name), None)
                print(f"      + {name}  {_fmt_size(size)}")
            for name in removed:
                print(f"      - {name}")

    if gone_e:
        print(f"\n  GONE ({len(gone_e)}):")
        for rid in gone_e:
            print(f"    {rid}")

    if not (new_e or upd_e or gone_e):
        print("\n  No changes since last run.")


def _print_full_list(repos: dict) -> None:
    """Print all repos sorted by downloads — used on first run."""
    by_dl = sorted(repos.items(), key=lambda x: x[1].get("downloads") or 0, reverse=True)
    for rid, rec in by_dl:
        _print_repo_line(rid, rec)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scout HuggingFace for new GGUF models useful for coding + context benchmarks",
    )
    parser.add_argument("--state", default=None,
                        help="State JSON path (default: output/hf-scout-state.json)")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN"),
                        help="HuggingFace API token (default: HF_TOKEN env var)")
    parser.add_argument("--limit", type=int, default=_REPOS_PER_QUERY,
                        help=f"Repos fetched per query (default: {_REPOS_PER_QUERY})")
    parser.add_argument("--no-save", action="store_true",
                        help="Print results without updating the state file")
    parser.add_argument("--show-all", action="store_true",
                        help="Also print the full repo list (useful on subsequent runs)")
    parser.add_argument("--queries", nargs="+", default=None,
                        help="Override default search queries")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print(
            "Error: huggingface_hub is not installed.\n"
            "Run:  source .venv/bin/activate && pip install huggingface_hub",
            file=sys.stderr,
        )
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent.parent
    state_path = Path(args.state) if args.state else script_dir / "output" / "hf-scout-state.json"
    queries = args.queries or SCOUT_QUERIES

    api = HfApi(token=args.token or None)

    old_state = _load_state(state_path)
    old_repos = old_state.get("repos", {})
    old_meta = old_state.get("meta", {})
    now = _now_iso()

    print("═" * 64)
    print("  HuggingFace GGUF Scout")
    if old_meta.get("last_run"):
        print(f"  Previous run   : {old_meta['last_run']}  ({len(old_repos)} repos)")
    else:
        print("  (first run — no previous state)")
    print(f"  Queries        : {len(queries)}")
    print(f"  State file     : {state_path}")
    print("═" * 64)
    print()

    new_repos = _scout(api, queries, args.limit)
    print(f"\n  Found {len(new_repos)} repos with GGUF files.")

    if old_repos:
        new_e, upd_e, gone_e = _compute_diff(old_repos, new_repos)
        _print_diff(new_e, upd_e, gone_e)
        delta = len(new_e) - len(gone_e)
        sign = "+" if delta >= 0 else ""
        print(f"\n  Total: {len(new_repos)} repos  "
              f"({sign}{delta} since {old_meta.get('last_run', '?')})")
        if args.show_all:
            print("\n  Full list:")
            _print_full_list(new_repos)
    else:
        print("\n  Full list (✓ fits 24 GB, ~ tight, ✗ needs multi-GPU):")
        _print_full_list(new_repos)

    # Preserve first_seen timestamps from prior state
    for rid, rec in new_repos.items():
        rec["first_seen"] = old_repos[rid].get("first_seen", now) if rid in old_repos else now
        rec["last_seen"] = now

    if args.no_save:
        print("\n  (--no-save: state file not updated)")
    else:
        _save_state(state_path, {
            "meta": {"version": 1, "last_run": now, "total_repos": len(new_repos)},
            "repos": new_repos,
        })
        print(f"\n  State saved → {state_path}")

    print()


if __name__ == "__main__":
    main()
