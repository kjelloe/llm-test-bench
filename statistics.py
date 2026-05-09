#!/usr/bin/env python3
"""
statistics.py — Aggregate benchmark results into a sharable dataset.

Reads output/*.json result files (or specified files) and produces a flat
dataset with one row per model per run (default) or one row per task per run
(--detail).  Useful for comparing results across hardware or model versions.

Usage:
    python3 statistics.py [OPTIONS] [FILE ...]

Options:
    --format {json,csv,markdown}   output format  (default: markdown)
    --out PATH                     write to file instead of stdout
    --detail                       one row per task (default: summary per model)
    FILE ...                       result JSON files  (default: output/*.json)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# ── Task difficulties (best-effort; ok if lib unavailable) ────────────────────
try:
    sys.path.insert(0, str(SCRIPT_DIR))
    from lib.tasks import TASK_MAP
    DIFFICULTIES: dict[str, int] = {t.id: t.difficulty for t in TASK_MAP.values()}
except Exception:
    DIFFICULTIES = {}


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_file(path: Path) -> tuple[list[dict], dict | None]:
    """Return (results, hardware) from a result JSON.  Raises on bad format."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        # old flat-list format; must contain result records
        if not data or "task" not in data[0]:
            raise ValueError("not a results file")
        return data, None
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        if not results or "task" not in results[0]:
            raise ValueError("not a results file")
        return results, data.get("hardware")
    raise ValueError("unrecognised file format")


# ── Hardware helpers ──────────────────────────────────────────────────────────

def _hw_gpu(hw: dict | None) -> str:
    """'RTX 5060 Ti 16GB' or ''."""
    if not hw:
        return ""
    gpus = hw.get("gpu") or []
    if not gpus:
        return ""
    g = gpus[0]
    vram = round(g.get("vram_total_mb", 0) / 1024)
    return f"{g.get('name', '')} {vram}GB".strip()


def _hw_cpu(hw: dict | None) -> str:
    return (hw or {}).get("cpu") or ""


def _hw_ram(hw: dict | None) -> float | str:
    return (hw or {}).get("ram_total_gb") or ""


def _hw_platform(hw: dict | None) -> str:
    return (hw or {}).get("platform") or ""


# ── Row builders ──────────────────────────────────────────────────────────────

def _run_date(path: Path) -> str:
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")


def _difficulty_summary(recs: list[dict]) -> str:
    """'L1:6/6 L2:4/5 L3:2/3' — skip levels with no tasks."""
    by_level: dict[int, list[bool]] = {}
    for r in recs:
        lvl = DIFFICULTIES.get(r["task"], 0)
        if lvl:
            by_level.setdefault(lvl, []).append(r["tests_pass"])
    parts = []
    for lvl in sorted(by_level):
        passes = sum(by_level[lvl])
        total = len(by_level[lvl])
        parts.append(f"L{lvl}:{passes}/{total}")
    return "  ".join(parts)


def summary_rows(path: Path, results: list[dict], hw: dict | None) -> list[dict]:
    """One row per (model, backend) pair."""
    run_date = _run_date(path)
    gpu = _hw_gpu(hw)
    cpu = _hw_cpu(hw)
    ram_gb = _hw_ram(hw)
    platform = _hw_platform(hw)

    # Group by model + backend
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        key = (r["model"], r.get("backend", "ollama"))
        groups.setdefault(key, []).append(r)

    rows = []
    for (model, backend), recs in groups.items():
        passed = sum(1 for r in recs if r["tests_pass"])
        total = len(recs)
        toks = [r["tok_per_s"] for r in recs if r.get("tok_per_s", 0) > 0]
        avg_tok = round(sum(toks) / len(toks), 1) if toks else 0.0
        total_wall = round(sum(r["wall_s"] for r in recs), 1)
        hf_repo = next((r["hf_repo"] for r in recs if r.get("hf_repo")), "")

        err_counts: dict[str, int] = {}
        for r in recs:
            k = r.get("error_kind") or ""
            if k:
                err_counts[k] = err_counts.get(k, 0) + 1

        rows.append({
            "source_file":      path.name,
            "run_date":         run_date,
            "gpu":              gpu,
            "cpu":              cpu,
            "ram_gb":           ram_gb,
            "platform":         platform,
            "model":            model,
            "backend":          backend,
            "hf_repo":          hf_repo,
            "tasks_passed":     passed,
            "tasks_total":      total,
            "pass_pct":         round(passed / total * 100, 1) if total else 0.0,
            "avg_tok_per_s":    avg_tok,
            "total_wall_s":     total_wall,
            "skill":            _difficulty_summary(recs),
            "ctx_truncated":    err_counts.get("CTX_TRUNCATED", 0),
            "no_blocks":        err_counts.get("NO_BLOCKS", 0),
            "tests_still_fail": err_counts.get("TESTS_STILL_FAIL", 0),
            "tool_error":       err_counts.get("TOOL_ERROR", 0),
        })
    return rows


def detail_rows(path: Path, results: list[dict], hw: dict | None) -> list[dict]:
    """One row per task record."""
    run_date = _run_date(path)
    gpu = _hw_gpu(hw)
    cpu = _hw_cpu(hw)
    ram_gb = _hw_ram(hw)

    rows = []
    for r in results:
        m = r.get("metrics") or {}
        rows.append({
            "source_file":        path.name,
            "run_date":           run_date,
            "gpu":                gpu,
            "cpu":                cpu,
            "ram_gb":             ram_gb,
            "model":              r["model"],
            "backend":            r.get("backend", "ollama"),
            "hf_repo":            r.get("hf_repo", ""),
            "task":               r["task"],
            "difficulty":         DIFFICULTIES.get(r["task"], ""),
            "pass":               r["tests_pass"],
            "error_kind":         r.get("error_kind") or "",
            "tok_per_s":          r.get("tok_per_s", 0.0),
            "wall_s":             r.get("wall_s", 0.0),
            "prompt_tokens":      m.get("prompt_eval_count", ""),
            "gen_tokens":         m.get("eval_count", ""),
            "num_ctx":            m.get("num_ctx", ""),
            "ctx_truncated":      r.get("ctx_truncated", False),
            "response_truncated": r.get("response_truncated", False),
        })
    return rows


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False)


def fmt_csv(rows: list[dict]) -> str:
    """Semicolon-delimited, every cell double-quoted (Nordic CSV)."""
    if not rows:
        return ""
    buf = io.StringIO()
    keys = list(rows[0].keys())
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(keys)
    for row in rows:
        writer.writerow([row.get(k, "") for k in keys])
    return buf.getvalue()


def fmt_markdown(rows: list[dict]) -> str:
    if not rows:
        return "_No results._\n"
    keys = list(rows[0].keys())
    # column widths
    widths = {k: len(k) for k in keys}
    for row in rows:
        for k in keys:
            widths[k] = max(widths[k], len(str(row.get(k, ""))))

    def _row(values: list[str]) -> str:
        cells = (f" {v:<{widths[k]}} " for k, v in zip(keys, values))
        return "|" + "|".join(cells) + "|"

    sep = "|" + "|".join("-" * (widths[k] + 2) for k in keys) + "|"
    lines = [
        _row(keys),
        sep,
        *(_row([str(row.get(k, "")) for k in keys]) for row in rows),
    ]
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark results into a sharable dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files", nargs="*", metavar="FILE",
        help="Result JSON files (default: all output/*.json)",
    )
    parser.add_argument(
        "--format", choices=["json", "csv", "markdown"], default="markdown",
        dest="fmt",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--out", metavar="PATH",
        help="Write to file instead of stdout",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="One row per task instead of one row per model",
    )
    args = parser.parse_args()

    # Resolve input files
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        output_dir = SCRIPT_DIR / "output"
        paths = sorted(p for p in output_dir.glob("*.json")
                       if p.name != "compare-history.json")
        if not paths:
            sys.exit("No result files found in output/")

    all_rows: list[dict] = []
    for path in paths:
        try:
            results, hw = load_file(path)
        except Exception as exc:
            print(f"Skipping {path.name}: {exc}", file=sys.stderr)
            continue
        rows = detail_rows(path, results, hw) if args.detail else summary_rows(path, results, hw)
        all_rows.extend(rows)

    if not all_rows:
        sys.exit("No data found.")

    formatters = {"json": fmt_json, "csv": fmt_csv, "markdown": fmt_markdown}
    output = formatters[args.fmt](all_rows)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
