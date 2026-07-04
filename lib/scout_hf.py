#!/usr/bin/env python3
"""Scout HuggingFace Hub for new models useful for coding + context benchmarks.

Two modes (selected via --vllm flag):
  GGUF mode (default): searches library:gguf, outputs models/*.txt lines.
  vLLM mode (--vllm):  searches library:transformers + AWQ/GPTQ/FP8 tags,
                       fetches config.json per repo, outputs models/*.vllm lines.

Both modes save state to output/ and diff against the previous snapshot.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Queries covering coding/instruction model families suitable for 24–96 GB VRAM.
# MoE-specific queries are included to surface large-but-fast models suited for
# 48 GB (2×24 GB) and 72 GB (3×24 GB) multi-GPU setups.
# Each query runs against the HF GGUF library tag; results are deduped by repo_id.
SCOUT_QUERIES: list[str] = [
    # ── Proven single-24 GB coding families ──
    "qwen3 coder instruct",
    "qwen3 instruct moe",
    "qwen2.5 coder instruct",
    "devstral coding",
    "deepseek-r1 instruct",
    "deepseek coder instruct",
    "gemma4 instruct",
    "gpt-oss",
    "codestral",
    "phi4 coding instruct",
    # ── MoE models targeting 48 GB / 72 GB tiers ──
    "mixture of experts instruct gguf",  # generic MoE catch-all
    "moe instruct gguf coding",          # coding-focused MoE
    "qwen3 A3B instruct",                # Qwen3 MoE A3B active-param variants
    "qwen3-next instruct",               # Qwen3-Next large MoE family
    "deepseek moe gguf",                 # DeepSeek-V2/V3 MoE series
    "glm instruct gguf",                 # GLM MoE (glm4.7-flash lineage)
    "llama4 instruct",                   # Llama 4 Scout / Maverick MoE
    "command-a gguf",                    # Cohere Command A (~111B MoE)
    "mixtral instruct gguf",             # Mixtral family
    "noctrex gguf",                      # noctrex MXFP4 MoE releases
    "mxfp4 gguf",                        # MXFP4-quantized MoE models (Ampere+)
]

_REPOS_PER_QUERY = 10
_PREFERRED_QUANTS = ["Q4_K_M", "IQ4_XS", "Q5_K_M", "Q4_K_S", "Q4_K", "Q8_0", "Q6_K"]
_MIN_FILE_BYTES = 100 * 1024 * 1024   # skip files < 100 MB (tiny header shards etc.)

# ── vLLM scout constants ──────────────────────────────────────────────────────

# Queries for vLLM-compatible (transformers) models. Run once per quant type.
VLLM_SCOUT_QUERIES: list[str] = [
    "qwen3 coder instruct",
    "qwen3 instruct",
    "qwen2.5 coder instruct",
    "deepseek-r1 distill instruct",
    "deepseek coder instruct",
    "gemma instruct",
    "llama instruct",
    "mistral instruct",
    "phi4 instruct",
    "devstral instruct",
    "glm instruct",
    "gpt-oss instruct",
]

# Priority order: AWQ > GPTQ > FP8. FP8 is native safetensors (no extra quant library).
_VLLM_QUANT_PRIORITY = ["awq", "gptq", "fp8"]

# GPU size assumed per tensor-parallel rank (24 GB cards).
_GPU_VRAM_GB = 24.0
# KV overhead: 10% of total VRAM tier reserved for KV cache at default context.
_KV_OVERHEAD_RATIO = 0.10
# Max context length emitted in .vllm lines (cap long-context models).
_MAX_CTX_EMIT = 131072
_SHARD_RE = re.compile(r'(-\d{5})-of-(\d{5})\.gguf$', re.IGNORECASE)
_QUANT_RE = re.compile(r'\b(IQ\d[_A-Z0-9]*|Q\d[_A-Z0-9]*|F16|BF16|MXFP4|FP8)\b', re.IGNORECASE)

# VRAM tiers: (display_label, comfortable_ceiling_gb, hard_max_gb)
# ✓ = fits with useful KV headroom, ~ = fits but KV is tight, ✗ = won't fit
# Comfortable ceilings leave ~4 GB/GPU free after weights for KV cache.
_VRAM_TIERS: list[tuple[str, float, float]] = [
    ("24",  20.0, 23.0),
    ("48",  44.0, 47.0),
    ("72",  65.0, 71.0),
    ("96",  90.0, 95.0),
]

# Substrings that indicate a MoE architecture (checked against repo_id + filenames).
_MOE_MARKERS: frozenset[str] = frozenset({
    "moe", "mixture", "expert", "a3b", "a2b", "a2.5b", "mxfp4", "sparse",
    "scout", "maverick",   # Llama 4 MoE variants
})

# Substrings in repo_id (lowercased) that flag a vision/multimodal model — skip for coding bench.
_VL_MARKERS: frozenset[str] = frozenset({
    "qwen3-vl", "qwen2-vl", "-vl-", "vision-language", "llava", "internvl",
    "cogvlm", "moondream", "idefics", "paligemma", "pixtral",
})


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


def _vram_tiers_str(size_bytes: int | None) -> str:
    """Return compact multi-tier VRAM fit string, e.g. '24✓ 48✓ 72~'."""
    if size_bytes is None:
        return ""
    gb = size_bytes / 1024 ** 3
    parts: list[str] = []
    for label, comfort, max_gb in _VRAM_TIERS:
        if gb <= comfort:
            parts.append(f"{label}✓")
        elif gb <= max_gb:
            parts.append(f"{label}~")
        # else: doesn't fit this tier — omit to keep output compact
    return " ".join(parts) if parts else "✗all"


def _is_moe(repo_id: str, files: list[dict]) -> bool:
    text = repo_id.lower() + " " + " ".join(f["name"].lower() for f in files)
    return any(m in text for m in _MOE_MARKERS)


def _total_size_for_suggested(files: list[dict], suggested_name: str | None) -> int | None:
    """Return total bytes for the suggested quant (sums all shards if multi-part)."""
    if not suggested_name:
        return None
    shard_info = _parse_shard(suggested_name)
    if not shard_info:
        return next((f["size"] for f in files if f["name"] == suggested_name), None)
    base, _, _ = shard_info
    total = sum(f.get("size") or 0 for f in files if _parse_shard(f["name"]) and _parse_shard(f["name"])[0] == base)
    return total if total > 0 else None


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
            sug_name = suggested["name"] if suggested else None
            total_bytes = _total_size_for_suggested(files, sug_name)
            found[rid] = {
                "downloads": getattr(repo, "downloads", None),
                "likes": getattr(repo, "likes", None),
                "files": files,
                "suggested_file": sug_name,
                "total_size_bytes": total_bytes,
                "is_moe": _is_moe(rid, files),
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
    # Use total_size_bytes (shard-summed) when available, fall back to single-file size
    size = rec.get("total_size_bytes") or _suggested_size(rec)
    tiers = _vram_tiers_str(size)
    size_str = _fmt_size(size) if size else ""
    moe_tag = " [MoE]" if rec.get("is_moe") else ""
    dl_str = f"  {dl}" if dl else ""
    size_part = f"  {size_str}{moe_tag}  {tiers}" if size_str else (moe_tag.strip() or "")
    print(f"{indent}{rid}{dl_str}{size_part}")
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


# ── vLLM helpers ──────────────────────────────────────────────────────────────

def _fetch_config(api, repo_id: str) -> dict:
    """Download config.json from repo into HF cache and return parsed dict."""
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=repo_id, filename="config.json",
            token=api.token, local_files_only=False,
        )
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _detect_quant(config: dict, repo_id: str = "") -> tuple[str, int]:
    """Return (quant_type, bits) from config.json, falling back to repo name heuristics."""
    qc = config.get("quantization_config") or {}
    qt = (qc.get("quant_type") or qc.get("quant_method") or "").lower()
    bits = int(qc.get("bits") or qc.get("num_bits") or 16)

    # AWQ / GPTQ are unambiguous — check first.
    if qt == "awq":
        return "awq", bits if bits < 16 else 4
    if qt in ("gptq", "gptq_marlin"):
        return "gptq", bits if bits < 16 else 4

    # Name-based check runs before FP8 checks: repos using "compressed-tensors" as
    # quant_method (vLLM's native wrapper) or torch_dtype=float8 may still be W4A16
    # or GPTQ/AWQ weight quantization. Repo name is authoritative for the weight format.
    name = repo_id.lower()
    if "awq" in name or "w4a16" in name:
        return "awq", 4
    if "gptq" in name:
        m = re.search(r'int(\d+)', name)
        return "gptq", int(m.group(1)) if m else 4

    # FP8: explicit quant_type, torch_dtype, or name — only if no GPTQ/AWQ name match above.
    if qt in ("fp8", "compressed-tensors"):
        return "fp8", 8
    if "float8" in str(config.get("torch_dtype", "")).lower():
        return "fp8", 8
    if "fp8" in name:
        return "fp8", 8

    if qt == "bitsandbytes":
        return "bnb", int(qc.get("load_in_4bit") and 4 or qc.get("load_in_8bit") and 8 or 16)
    return "bf16", 16


def _is_moe_config(config: dict) -> bool:
    num_experts = config.get("num_experts") or config.get("num_local_experts") or 0
    return int(num_experts) > 1


def _estimate_params(config: dict) -> int | None:
    """Rough total parameter count from architecture fields in config.json."""
    hidden = config.get("hidden_size")
    layers = config.get("num_hidden_layers")
    inter = config.get("intermediate_size")
    vocab = config.get("vocab_size")
    if not all([hidden, layers, inter, vocab]):
        return None
    num_heads = config.get("num_attention_heads") or 1
    num_kv = config.get("num_key_value_heads") or num_heads
    head_dim = hidden // num_heads
    num_experts = int(config.get("num_experts") or config.get("num_local_experts") or 1)
    attn = hidden * hidden + 2 * num_kv * head_dim * hidden + hidden * hidden
    ffn = num_experts * 3 * hidden * inter  # all expert weights are stored
    return int(vocab * hidden + layers * (attn + ffn) + hidden)


def _active_params(total: int, config: dict) -> int:
    """For MoE: scale total by active-expert ratio for throughput estimation."""
    num_experts = int(config.get("num_experts") or config.get("num_local_experts") or 1)
    num_active = int(config.get("num_experts_per_tok") or config.get("num_selected_experts") or 1)
    if num_experts <= 1:
        return total
    layers = config.get("num_hidden_layers") or 1
    hidden = config.get("hidden_size") or 1
    inter = config.get("intermediate_size") or 1
    num_heads = config.get("num_attention_heads") or 1
    num_kv = config.get("num_key_value_heads") or num_heads
    head_dim = hidden // num_heads
    attn_per_layer = hidden * hidden + 2 * num_kv * head_dim * hidden + hidden * hidden
    # Recompute with active experts only
    ffn_active = num_active * 3 * hidden * inter
    return int(hidden * config.get("vocab_size", 32000) + layers * (attn_per_layer + ffn_active) + hidden)


def _vllm_vram_gb(total_params: int, quant_bits: int, vram_tier_gb: float) -> float:
    model_gb = (quant_bits * total_params) / 8 / 1e9
    return model_gb + _KV_OVERHEAD_RATIO * vram_tier_gb


def _derive_tp(vram_est_gb: float, num_kv_heads: int) -> int:
    """Return smallest TP where model fits (24 GB/rank) and num_kv_heads is divisible."""
    for tp in [1, 2, 3, 4]:
        tier = tp * _GPU_VRAM_GB
        if vram_est_gb <= tier * 0.90 and num_kv_heads % tp == 0:
            return tp
    return 4


def _search_vllm_repos(api, query: str, quant: str, limit: int) -> list:
    try:
        results = list(api.list_models(
            search=query,
            filter=["transformers", "text-generation", quant],
            limit=max(limit * 4, 20),
        ))
        # Exclude repos that are primarily GGUF (double-published repos).
        results = [r for r in results if "gguf" not in (getattr(r, "tags") or [])]
        results.sort(key=lambda m: getattr(m, "downloads", 0) or 0, reverse=True)
        return results[:limit]
    except Exception:
        return []


def _emit_vllm_lines(repo_id: str, num_params: int | None, config: dict) -> list[str]:
    """Return list of comment lines suitable for models/*.vllm."""
    if not num_params:
        return [f"# {repo_id}  (param count unknown — config.json incomplete)"]

    quant_type, quant_bits = _detect_quant(config, repo_id)
    is_moe = _is_moe_config(config)
    num_kv_heads = int(config.get("num_key_value_heads") or config.get("num_attention_heads") or 8)
    max_pos = int(config.get("max_position_embeddings") or 32768)
    max_ctx = min(max_pos, _MAX_CTX_EMIT)

    vram_est = _vllm_vram_gb(num_params, quant_bits, _GPU_VRAM_GB)
    tp = _derive_tp(vram_est, num_kv_heads)
    vram_total = tp * _GPU_VRAM_GB

    # Slug: owner/Repo-Name → owner-reponame for brevity
    slug = repo_id.replace("/", "-").lower()

    kv_param = "kv_cache_dtype=fp8," if quant_type in ("awq", "gptq") else ""
    line = (
        f"# {slug}  -  "
        f"tp={tp},dtype=auto,{kv_param}"
        f"gpu_mem_util=0.94,enable_prefix_caching,max_model_len={max_ctx}"
        f"  hf:{repo_id}"
    )

    num_experts = int(config.get("num_experts") or config.get("num_local_experts") or 1)
    num_active = int(config.get("num_experts_per_tok") or config.get("num_selected_experts") or 1)
    moe_note = f"MoE: {num_params / 1e9:.0f}B total, {_active_params(num_params, config) / 1e9:.0f}B active | " if is_moe else ""
    arch_note = f"{quant_type.upper()} Int{quant_bits}" if quant_bits < 16 else quant_type.upper()
    model_type = "MoE" if is_moe else "dense"
    vram_note = f"# [VRAM estimate: ~{vram_est:.0f} GB | {arch_note} | {model_type}]"

    return [line, vram_note]


def _scout_vllm(api, queries: list[str], repos_per_query: int) -> dict[str, dict]:
    """Search for transformers AWQ/GPTQ/FP8 repos; return {repo_id: record}."""
    found: dict[str, dict] = {}
    for quant in _VLLM_QUANT_PRIORITY:
        print(f"\n  ── {quant.upper()} ──")
        for query in queries:
            print(f"  {query!r:38s} … ", end="", flush=True)
            repos = _search_vllm_repos(api, query, quant, repos_per_query)
            added = 0
            for repo in repos:
                rid = repo.id
                if rid in found:
                    found[rid]["source_queries"].append(f"{quant}:{query}")
                    continue
                if any(m in rid.lower() for m in _VL_MARKERS):
                    continue
                config = _fetch_config(api, rid)
                if not config:
                    continue
                detected_quant, bits = _detect_quant(config, rid)
                if detected_quant not in _VLLM_QUANT_PRIORITY and detected_quant != "bf16":
                    continue
                # Try to get param count from safetensors metadata first.
                num_params: int | None = None
                try:
                    info = api.model_info(rid, expand=["safetensors"])
                    st = getattr(info, "safetensors", None) or {}
                    num_params = st.get("total") if st else None
                except Exception:
                    pass
                if not num_params:
                    num_params = _estimate_params(config)
                is_moe = _is_moe_config(config)
                found[rid] = {
                    "downloads": getattr(repo, "downloads", None),
                    "likes": getattr(repo, "likes", None),
                    "quant_type": detected_quant,
                    "quant_bits": bits,
                    "num_params": num_params,
                    "is_moe": is_moe,
                    "config": config,
                    "source_queries": [f"{quant}:{query}"],
                }
                added += 1
            print(f"{len(repos)} repos  (+{added} new)")
    return found


def _print_vllm_repo(rid: str, rec: dict) -> None:
    dl = _fmt_dl(rec.get("downloads"))
    num_params = rec.get("num_params")
    param_str = f"  {num_params / 1e9:.1f}B" if num_params else ""
    moe_tag = " [MoE]" if rec.get("is_moe") else ""
    qt = rec.get("quant_type", "?").upper()
    print(f"    {rid}{f'  {dl}' if dl else ''}{param_str}  {qt}{moe_tag}")
    for line in _emit_vllm_lines(rid, num_params, rec.get("config", {})):
        print(f"      {line}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scout HuggingFace for new models useful for coding + context benchmarks",
    )
    parser.add_argument("--vllm", action="store_true",
                        help="Scout vLLM-compatible models (AWQ/GPTQ/FP8 transformers) instead of GGUF")
    parser.add_argument("--state", default=None,
                        help="State JSON path (default: output/hf-scout-state[-vllm].json)")
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
    default_state = "hf-scout-vllm-state.json" if args.vllm else "hf-scout-state.json"
    state_path = Path(args.state) if args.state else script_dir / "output" / default_state

    api = HfApi(token=args.token or None)
    old_state = _load_state(state_path)
    old_repos = old_state.get("repos", {})
    old_meta = old_state.get("meta", {})
    now = _now_iso()

    # ── vLLM branch ───────────────────────────────────────────────────────────
    if args.vllm:
        queries = args.queries or VLLM_SCOUT_QUERIES
        print("═" * 64)
        print("  HuggingFace vLLM Scout  (AWQ / GPTQ / FP8 transformers)")
        if old_meta.get("last_run"):
            print(f"  Previous run   : {old_meta['last_run']}  ({len(old_repos)} repos)")
        else:
            print("  (first run — no previous state)")
        print(f"  Queries        : {len(queries)}  ×  {len(_VLLM_QUANT_PRIORITY)} quant types")
        print(f"  State file     : {state_path}")
        print("═" * 64)
        print()

        new_repos = _scout_vllm(api, queries, args.limit)
        print(f"\n  Found {len(new_repos)} vLLM-compatible repos.")

        by_dl = sorted(new_repos.items(), key=lambda x: x[1].get("downloads") or 0, reverse=True)
        if old_repos:
            new_e = [(r, d) for r, d in by_dl if r not in old_repos]
            gone_e = [r for r in old_repos if r not in new_repos]
            if new_e:
                print(f"\n  NEW ({len(new_e)}):")
                for rid, rec in new_e:
                    _print_vllm_repo(rid, rec)
            if gone_e:
                print(f"\n  GONE ({len(gone_e)}):")
                for rid in gone_e:
                    print(f"    {rid}")
            if not new_e and not gone_e:
                print("\n  No changes since last run.")
            delta = len(new_e) - len(gone_e)
            sign = "+" if delta >= 0 else ""
            print(f"\n  Total: {len(new_repos)} repos  ({sign}{delta} since {old_meta.get('last_run', '?')})")
            if args.show_all:
                print("\n  Full list:")
                for rid, rec in by_dl:
                    _print_vllm_repo(rid, rec)
        else:
            print("\n  Full list:")
            for rid, rec in by_dl:
                _print_vllm_repo(rid, rec)

        for rid, rec in new_repos.items():
            rec["first_seen"] = old_repos[rid].get("first_seen", now) if rid in old_repos else now
            rec["last_seen"] = now
            # Don't persist full config.json in state (large); keep summary only.
            rec.pop("config", None)

        if args.no_save:
            print("\n  (--no-save: state file not updated)")
        else:
            _save_state(state_path, {
                "meta": {"version": 1, "last_run": now, "total_repos": len(new_repos)},
                "repos": new_repos,
            })
            print(f"\n  State saved → {state_path}")
        print()
        return

    # ── GGUF branch (original behaviour) ──────────────────────────────────────
    queries = args.queries or SCOUT_QUERIES

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
        print("\n  Full list (VRAM tiers: 24/48/72/96 GB — ✓ comfortable, ~ tight KV, omitted = won't fit; [MoE] = MoE architecture):")
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
