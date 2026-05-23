#!/usr/bin/env python3
"""
estimate_vram.py — VRAM scalability estimation table.

Reads benchmark result files (output/*.json), extracts per-model performance
data measured on the anchor hardware (default: any single 24 GB GPU run), then
applies heuristic scaling rules to estimate throughput at other VRAM tiers.

Usage:
    python3 lib/estimate_vram.py [OPTIONS] [FILE ...]
    ./statistics.sh --estimate-vram [OPTIONS] [FILE ...]

Options:
    --format {markdown,csv,json}   output format (default: markdown)
    --out PATH                     write to file instead of stdout
    --anchor-vram N                GB of anchor hardware (default: 24)
    --ctx {8k,128k,both}           context columns to show (default: both)
    FILE ...                       result files (default: output/*.json)

Estimation logic
----------------
24 V (anchor): actual measured tok/s from result files.
16 V single:   model fits → anchor * BW_16V_FACTOR (≈ 0.80, bandwidth-ratio
               estimate for a typical 16 GB card vs RTX 3090).
               model doesn't fit → RAM-hybrid mode ≈ anchor * max(0.20,
               usable_vram / weight * 0.27).
Multi-GPU:     anchor * DUAL_FACTOR (≈ 0.87, PCIe sharding overhead).
               Exception: if model couldn't fit on single GPU but fits on dual,
               estimate close to full anchor speed (big speedup vs RAM).
128 k context: SKIPPED when weight_gb + kv128k_gb > tier_usable_gb.
               If anchor was SLOW (< SLOW_THRESHOLD tok/s) but tier has room,
               estimate via bandwidth ratio: anchor_8k * factor *
               weight_mb / (weight_mb + kv128k_mb).

All estimates are marked with ~ prefix. Measured anchor values are plain numbers.
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import io
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent

# ── Tier definitions ──────────────────────────────────────────────────────────
# (label, total_vram_gb, gpu_count)
TIERS = [
    ("16V",   16, 1),
    ("24V",   24, 1),   # anchor tier by default
    ("2x16V", 32, 2),
    ("2x24V", 48, 2),
    ("2x32V", 64, 2),
]

# ── Scaling constants ─────────────────────────────────────────────────────────
_USABLE           = 0.90    # usable fraction of rated VRAM
_BW_16V_FACTOR    = 0.80    # bandwidth ratio: typical 16 GB GPU vs RTX 3090
_DUAL_FACTOR      = 0.87    # PCIe tensor-parallel overhead for 2-GPU split
_RAM_SCALE        = 0.27    # used_vram/model * RAM_SCALE = hybrid speed fraction
_RAM_MAX_FACTOR   = 0.20    # cap: hybrid speed never > 20% of GPU-resident speed
_SLOW_THRESHOLD   = 10.0    # tok/s below which 128k is treated as SLOW / unusable

# ── Models permanently in RAM-hybrid mode (weight >> any single GPU) ──────────
# Map ollama name → approx full weight GB (GPU-resident fraction is much smaller).
_HYBRID_MODELS: dict[str, float] = {
    "gpt-oss:120b":    70.0,
    "llama4-scout:17b": 60.0,
}


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_file(path: Path) -> tuple[list[dict], dict | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        if not data or "task" not in data[0]:
            raise ValueError("not a results file")
        return data, None
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        if not results or "task" not in results[0]:
            raise ValueError("not a results file")
        return results, data.get("hardware")
    raise ValueError("unrecognised file format")


def _total_vram_gb(hw: dict | None) -> float:
    gpus = (hw or {}).get("gpu") or []
    return sum(g.get("vram_total_mb", 0) for g in gpus) / 1024


def _gpu_count(hw: dict | None) -> int:
    return len((hw or {}).get("gpu") or [])


# ── Per-model anchor extraction ───────────────────────────────────────────────

_CONTEXT_TASKS = {
    "context_8k", "context_16k", "context_32k", "context_64k",
    "context_128k", "context_256k",
    "multihop_forward", "multihop_reverse", "distractor_notes",
}

# Any task NOT in _CONTEXT_TASKS is treated as short-context (for tps_8k anchor).
# This includes coding, data, and L6 stepped/full tasks.


def _extract_anchors(results: list[dict]) -> dict[str, dict]:
    """Return per-model anchor data dict from one result file.

    Keys per model:
      weight_mb       GPU-resident model weight (from gpu_snapshots delta)
      kv128k_mb       KV cache size at 131072 ctx (snapshot delta vs coding weight)
      tps_8k          avg tok/s on coding tasks
      tps_128k        tok/s at context_128k (0 if SKIPPED or not run)
      ek_128k         error_kind for context_128k ('SKIPPED_CTX', None, …)
      slow_128k       bool – PASS_BUT_SLOW at context_128k
      tasks_passed    count
      tasks_total     count
    """
    by_model: dict[str, dict] = {}

    for r in results:
        m = r["model"]
        d = by_model.setdefault(m, {
            "weight_mbs": [],       # one per result record that has snapshot data
            "after_128k_mb": None,
            "tps_coding": [],
            "tps_128k": 0.0,
            "ek_128k": None,
            "slow_128k": False,
            "tasks_passed": 0,
            "tasks_total": 0,
        })
        d["tasks_total"] += 1
        if r.get("tests_pass"):
            d["tasks_passed"] += 1

        snap = r.get("gpu_snapshots") or {}
        before_mb = (snap.get("before_load") or {}).get("vram_used_mb")
        after_mb  = (snap.get("after_load")  or {}).get("vram_used_mb")
        if before_mb is not None and after_mb is not None and after_mb > before_mb:
            d["weight_mbs"].append(after_mb - before_mb)

        task = r["task"]
        tps  = r.get("tok_per_s", 0.0)

        if task == "context_128k":
            d["tps_128k"]   = tps
            d["ek_128k"]    = r.get("error_kind")
            d["slow_128k"]  = bool(r.get("slow"))
            if after_mb is not None:
                d["after_128k_mb"] = after_mb

        elif task not in _CONTEXT_TASKS and tps > 0:
            d["tps_coding"].append(tps)

    # Consolidate
    anchors: dict[str, dict] = {}
    for m, d in by_model.items():
        weight_mb = round(sum(d["weight_mbs"]) / len(d["weight_mbs"])) if d["weight_mbs"] else None

        kv128k_mb: int | None = None
        if weight_mb is not None and d["after_128k_mb"] is not None:
            kv128k_mb = max(0, d["after_128k_mb"] - weight_mb)

        tps_8k = round(sum(d["tps_coding"]) / len(d["tps_coding"]), 1) if d["tps_coding"] else 0.0

        anchors[m] = {
            "weight_mb":    weight_mb,
            "kv128k_mb":    kv128k_mb,
            "tps_8k":       tps_8k,
            "tps_128k":     round(d["tps_128k"], 1),
            "ek_128k":      d["ek_128k"],
            "slow_128k":    d["slow_128k"],
            "tasks_passed": d["tasks_passed"],
            "tasks_total":  d["tasks_total"],
        }
    return anchors


def _merge_anchors(all_anchors: list[dict[str, dict]]) -> dict[str, dict]:
    """Merge per-file anchors; prefer highest tps_8k anchor per model."""
    merged: dict[str, dict] = {}
    for anchors in all_anchors:
        for model, data in anchors.items():
            if model not in merged or data["tps_8k"] > merged[model]["tps_8k"]:
                merged[model] = data
    return merged


# ── Estimation ────────────────────────────────────────────────────────────────

def _fmt(val: float | None, is_estimate: bool = True) -> str:
    if val is None or val <= 0:
        return "—"
    s = f"~{int(round(val))}" if is_estimate else f"{val:.1f}"
    return s


def _cell_8k(model: str, a: dict, tier_vram_gb: int, gpu_count: int,
             anchor_vram_gb: int) -> str:
    weight_mb = a["weight_mb"]
    tps_8k    = a["tps_8k"]

    # Hybrid models: always RAM-bound
    full_weight_gb = _HYBRID_MODELS.get(model)
    if full_weight_gb is not None:
        if tps_8k > 0:
            return _fmt(tps_8k, is_estimate=(tier_vram_gb != anchor_vram_gb or gpu_count != 1))
        return "~" + str(int(full_weight_gb)) + "GB hybrid"

    if weight_mb is None or tps_8k <= 0:
        return "—"

    usable_mb = tier_vram_gb * 1024 * _USABLE

    if gpu_count == 1:
        if tier_vram_gb == anchor_vram_gb:
            return _fmt(tps_8k, is_estimate=False)   # anchor: real value
        if weight_mb <= usable_mb:
            factor = _BW_16V_FACTOR if tier_vram_gb < anchor_vram_gb else 1.02
            return _fmt(tps_8k * factor)
        else:
            # RAM hybrid
            ram_f = min(_RAM_MAX_FACTOR, (usable_mb / weight_mb) * _RAM_SCALE)
            return _fmt(tps_8k * ram_f)
    else:
        # dual GPU
        if weight_mb <= usable_mb:
            return _fmt(tps_8k * _DUAL_FACTOR)
        else:
            # model was RAM-hybrid on single, now fits on dual → big speedup
            return _fmt(tps_8k * _DUAL_FACTOR * 0.92)


def _cell_128k(model: str, a: dict, tier_vram_gb: int, gpu_count: int,
               anchor_vram_gb: int) -> str:
    weight_mb  = a["weight_mb"]
    kv128k_mb  = a["kv128k_mb"]
    tps_8k     = a["tps_8k"]
    tps_128k   = a["tps_128k"]
    ek_128k    = a["ek_128k"]
    slow_128k  = a["slow_128k"]

    full_weight_gb = _HYBRID_MODELS.get(model)
    if full_weight_gb is not None:
        # hybrid: usually SLOW but can do 128k if RAM is large enough
        if tps_128k > 0 and not (slow_128k and tps_128k < _SLOW_THRESHOLD):
            return _fmt(tps_128k, is_estimate=(tier_vram_gb != anchor_vram_gb or gpu_count != 1))
        if tps_128k > 0:
            return f"~{tps_128k:.0f} SLOW"
        return "—"

    if weight_mb is None:
        return "—"

    is_anchor = (tier_vram_gb == anchor_vram_gb and gpu_count == 1)

    # Anchor: always trust actual measurements over the capacity formula.
    # The model ran (or was config-skipped), so use that result directly.
    if is_anchor:
        if ek_128k == "SKIPPED_CTX":
            return "SKIP_CTX"  # max_ctx config cap, not VRAM
        if ek_128k in ("SKIPPED_VRAM",):
            return "SKIPPED"
        if tps_128k > 0 and not slow_128k:
            return _fmt(tps_128k, is_estimate=False)
        if slow_128k and tps_128k >= _SLOW_THRESHOLD:
            return f"{tps_128k:.1f}~"   # measured but slow
        if tps_128k > 0:
            return f"{tps_128k:.1f} SLOW"
        return "—"

    usable_mb = tier_vram_gb * 1024 * _USABLE

    # KV fallback: if kv128k_mb unknown, use a GQA-optimistic 2.5 GB estimate
    kv_mb = kv128k_mb if kv128k_mb is not None else 2560

    # For other tiers: use measured total (weight + kv from anchor) to check fit.
    # This is more accurate than the formula-based estimate for the anchor tier itself.
    total_needed_mb = weight_mb + kv_mb

    if total_needed_mb > usable_mb:
        return "SKIPPED"

    # Non-anchor tier: model fits here; estimate speed
    if gpu_count == 1:
        factor = _BW_16V_FACTOR if tier_vram_gb < anchor_vram_gb else 1.02
    else:
        factor = _DUAL_FACTOR

    # If anchor 128k was SLOW (KV spill) or SKIPPED_CTX, estimate from 8k speed
    anchor_128k_bad = (slow_128k and tps_128k < _SLOW_THRESHOLD) or \
                       ek_128k in ("SKIPPED_CTX", "SKIPPED_VRAM") or \
                       tps_128k <= 0
    if anchor_128k_bad:
        if tps_8k <= 0:
            return "—"
        # KV-ratio: speed falls as KV fills bandwidth
        kv_ratio = weight_mb / max(weight_mb + kv_mb, 1)
        return _fmt(tps_8k * factor * kv_ratio)
    else:
        # Anchor had good 128k; scale it
        return _fmt(tps_128k * factor)


# ── Table builders ────────────────────────────────────────────────────────────

def build_rows(anchors: dict[str, dict], anchor_vram_gb: int,
               show_ctx: str) -> list[dict]:
    rows = []
    for model, a in anchors.items():
        passed = a["tasks_passed"]
        total  = a["tasks_total"]
        pct    = f"{round(passed / total * 100)}%" if total else "—"

        row: dict = {"model": model, "pass%": pct}

        if show_ctx in ("8k", "both"):
            for label, vram, gpus in TIERS:
                row[f"{label} (8k)"] = _cell_8k(model, a, vram, gpus, anchor_vram_gb)

        if show_ctx in ("128k", "both"):
            for label, vram, gpus in TIERS:
                row[f"{label} (128k)"] = _cell_128k(model, a, vram, gpus, anchor_vram_gb)

        rows.append(row)

    # Sort: 8k anchor speed descending, then model name
    anchor_col = f"24V (8k)"
    def _sort_key(r: dict) -> tuple:
        v = r.get(anchor_col, "0")
        try:
            return (-float(str(v).lstrip("~").split()[0]), r["model"])
        except (ValueError, IndexError):
            return (0.0, r["model"])

    return sorted(rows, key=_sort_key)


# ── Notes ─────────────────────────────────────────────────────────────────────

_NOTES = """\
Estimation notes
----------------
Anchor:       Real measurements from a single 24 GB GPU (RTX 3090, llama-server).
              Values without ~ are from actual benchmark runs.
~values:      Estimated from anchor using heuristic scaling factors.
16 V (8k):    Model fits → anchor × 0.80 (bandwidth ratio, varies by GPU model).
              Model exceeds 16 GB → RAM-hybrid: ~anchor × min(0.20, vram/weight × 0.27).
2×N V (8k):   anchor × 0.87 (PCIe tensor-parallel overhead).
128k SKIPPED: weight_GB + KV_cache_GB > tier_usable_GB.
              KV cache sizes measured from VRAM snapshots at context_128k.
128k SLOW:    Model fits in VRAM but KV spills slightly (e.g. qwen3-coder:30b on 24V).
SKIP_CTX:     Context limited by model config (max_ctx flag), not VRAM.
Hybrid:       gpt-oss:120b keeps ~70 GB in RAM regardless of GPU tier.
Multi-GPU:    NVLink between cards removes PCIe bottleneck — real speeds may be higher.
              KV headroom from pooled VRAM can unlock 128k context for previously SLOW models.
"""


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_markdown(rows: list[dict]) -> str:
    if not rows:
        return "_No data._\n"
    keys = list(rows[0].keys())
    widths = {k: len(k) for k in keys}
    for row in rows:
        for k in keys:
            widths[k] = max(widths[k], len(str(row.get(k, ""))))

    def _row(vals: list[str]) -> str:
        return "|" + "|".join(f" {v:<{widths[k]}} " for k, v in zip(keys, vals)) + "|"

    sep = "|" + "|".join("-" * (widths[k] + 2) for k in keys) + "|"
    lines = [_row(keys), sep] + [_row([str(r.get(k, "")) for k in keys]) for r in rows]
    return "\n".join(lines) + "\n\n" + _NOTES


def fmt_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    keys = list(rows[0].keys())
    w = csv_mod.writer(buf, delimiter=";", quoting=csv_mod.QUOTE_ALL, lineterminator="\n")
    w.writerow(keys)
    for row in rows:
        w.writerow([row.get(k, "") for k in keys])
    return buf.getvalue()


def fmt_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="VRAM scalability estimation table from benchmark results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_NOTES,
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="Result JSON files (default: all output/*.json)")
    parser.add_argument("--format", choices=["markdown", "csv", "json"],
                        default="markdown", dest="fmt")
    parser.add_argument("--out", metavar="PATH",
                        help="Write output to file instead of stdout")
    parser.add_argument("--anchor-vram", type=int, default=24, metavar="N",
                        help="Treat N-GB single-GPU results as anchor (default: 24)")
    parser.add_argument("--ctx", choices=["8k", "128k", "both"], default="both",
                        help="Context columns to include (default: both)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print every file considered, including those skipped")
    args = parser.parse_args()

    _NON_RESULT = {"compare-history.json", "hf-scout-state.json"}
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        output_dir = SCRIPT_DIR / "output"
        paths = sorted(p for p in output_dir.glob("*.json")
                       if p.name not in _NON_RESULT)
        if not paths:
            sys.exit("No result files found in output/")

    all_anchors: list[dict[str, dict]] = []
    used: list[str] = []
    for path in paths:
        try:
            results, hw = _load_file(path)
        except Exception as exc:
            if args.verbose:
                print(f"skip {path.name}: {exc}", file=sys.stderr)
            continue
        vram = _total_vram_gb(hw)
        gpus = _gpu_count(hw)
        if gpus != 1 or round(vram) != args.anchor_vram:
            if args.verbose:
                print(f"skip {path.name}: {vram:.0f} GB {gpus}-GPU (need {args.anchor_vram} GB single)",
                      file=sys.stderr)
            continue
        used.append(f"{path.name} ({vram:.0f} GB)")
        all_anchors.append(_extract_anchors(results))

    print(f"Anchor files ({len(used)}): {', '.join(used) if used else 'none'}", file=sys.stderr)

    if not all_anchors:
        sys.exit(
            f"No {args.anchor_vram} GB single-GPU result files found. "
            f"Specify files explicitly or use --anchor-vram to change the anchor tier."
        )

    anchors = _merge_anchors(all_anchors)
    rows = build_rows(anchors, args.anchor_vram, args.ctx)

    if not rows:
        sys.exit("No model data found.")

    formatters = {"markdown": fmt_markdown, "csv": fmt_csv, "json": fmt_json}
    output = formatters[args.fmt](rows)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
