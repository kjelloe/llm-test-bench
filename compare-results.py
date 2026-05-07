#!/usr/bin/env python3
"""Compare two bench result JSON files side by side.

Prints:
  1. A speed summary table (tok/s and wall time per model, with speedup ratio).
  2. The full per-task comparison table with [ollama] / [ls] rows.

Usage:
  ./compare-results.sh output/results-compare.json output/results-compare-ls.json
  ./compare-results.sh output/results-default.json output/results-default-ls.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.reporting import load_results, print_comparison_table, print_summary


def _speed_summary(results: list[dict]) -> None:
    """Print a compact tok/s + wall-time comparison grouped by base model name."""
    from collections import defaultdict

    # Group by (base_model, backend)
    stats: dict[tuple[str, str], dict] = defaultdict(lambda: {"toks": [], "walls": [], "passed": 0, "total": 0})
    for r in results:
        key = (r["model"], r.get("backend", "ollama"))
        s = stats[key]
        s["total"] += 1
        if r.get("tests_pass"):
            s["passed"] += 1
        if r.get("tok_per_s", 0) > 0:
            s["toks"].append(r["tok_per_s"])
        s["walls"].append(r.get("wall_s", 0))

    # Find base models that appear in more than one backend
    backends_per_model: dict[str, set[str]] = defaultdict(set)
    for model, backend in stats:
        backends_per_model[model].add(backend)

    comparable = sorted(
        m for m, bs in backends_per_model.items() if len(bs) > 1
    )
    if not comparable:
        # Still show all models even if only one backend
        comparable = sorted({m for m, _ in stats})

    # Collect all backends in result order
    all_backends = list(dict.fromkeys(r.get("backend", "ollama") for r in results))

    col_w = max(len(m) for m in comparable)
    be_w  = max(len(b) for b in all_backends)
    HDR   = f"{'Model':<{col_w}}  {'Backend':<{be_w}}  {'pass':>4}  {'avg tok/s':>9}  {'tot wall':>8}"

    print()
    print("=" * len(HDR))
    print("SPEED SUMMARY")
    print("=" * len(HDR))
    print(HDR)
    print("-" * len(HDR))

    for model in comparable:
        rows = []
        for backend in all_backends:
            s = stats.get((model, backend))
            if s is None:
                continue
            avg_toks = sum(s["toks"]) / len(s["toks"]) if s["toks"] else 0.0
            tot_wall = sum(s["walls"])
            rows.append((backend, s["passed"], s["total"], avg_toks, tot_wall))

        for i, (backend, passed, total, avg_toks, tot_wall) in enumerate(rows):
            tok_str  = f"{avg_toks:9.1f}" if avg_toks > 0 else "        -"
            wall_str = f"{tot_wall:7.1f}s"
            print(f"{'  ' if i else ''}{model if i == 0 else '':<{col_w}}  {backend:<{be_w}}  {passed:>2}/{total:<2}  {tok_str}  {wall_str}")

        # Print speedup line when exactly two backends
        if len(rows) == 2:
            _, _, _, toks_a, wall_a = rows[0]
            _, _, _, toks_b, wall_b = rows[1]
            if toks_a > 0 and toks_b > 0:
                ratio = toks_b / toks_a
                sign  = "+" if ratio >= 1 else ""
                print(f"  {'':>{col_w}}  {'→ speedup':<{be_w}}  {'':>4}  {sign}{(ratio-1)*100:8.0f}%")

        print()

    print("-" * len(HDR))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    results: list[dict] = []
    hardware: dict | None = None
    for path in sys.argv[1:]:
        r, hw = load_results(path)
        results.extend(r)
        if hw:
            hardware = hw  # use last file's hw snapshot; both should be same machine

    _speed_summary(results)
    print_comparison_table(results, hardware=hardware)
    print_summary(results)


if __name__ == "__main__":
    main()
