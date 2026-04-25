import json
from collections import defaultdict
from pathlib import Path


def write_results(results: list[dict], path: str) -> None:
    Path(path).write_text(json.dumps(results, indent=2), encoding="utf-8")


def print_comparison_table(results: list[dict]) -> None:
    models = list(dict.fromkeys(r["model"] for r in results))
    tasks  = list(dict.fromkeys(r["task"]  for r in results))
    idx    = {(r["model"], r["task"]): r for r in results}

    # Assumed speed rank: position in --models arg order (1 = fastest assumed)
    speed_rank = {m: i + 1 for i, m in enumerate(models)}

    # Column widths
    # cell layout: "PASS  " (6) + "  42.3t/s" (9) + "  " (2) + "  14.2s" (7) = 24
    model_w = max(len("Model"), max(len(m) for m in models))
    CELL_W  = 24   # "PASS  1234.5t/s    14.2s"
    SUM_W   = 25   # "3/3  1234.5t/s  1234.5s"
    SPD_W   = 3    # "1" – "9", centred

    def cell(r: dict | None) -> str:
        if r is None:
            return " " * CELL_W
        ok  = "PASS" if r["tests_pass"] else "FAIL"
        tok = f"{r['tok_per_s']:6.1f}t/s" if r.get("tok_per_s", 0) > 0 else "     -   "
        s   = f"{r['wall_s']:6.1f}s"
        return f"{ok}  {tok}  {s}"

    def summary(recs: list[dict | None]) -> str:
        passed  = sum(1 for r in recs if r and r["tests_pass"])
        total_s = sum(r["wall_s"] for r in recs if r)
        toks    = [r["tok_per_s"] for r in recs if r and r.get("tok_per_s", 0) > 0]
        avg_tok = sum(toks) / len(toks) if toks else 0.0
        return f"{passed}/{len(tasks)}  {avg_tok:6.1f}t/s  {total_s:7.1f}s"

    bar = (
        "+" + "-" * (model_w + 2)
        + "+" + "-" * (SPD_W + 2)
        + ("+" + "-" * (CELL_W + 2)) * len(tasks)
        + "+" + "-" * (SUM_W + 2) + "+"
    )

    print()
    print("=" * len(bar))
    print("COMPARISON TABLE  (Spd: assumed rank 1=fastest)")
    print("=" * len(bar))
    print(bar)

    # Task name headers
    task_hdrs = "".join(f"| {t:<{CELL_W}} " for t in tasks)
    print(f"| {'Model':<{model_w}} | {'Spd':^{SPD_W}} {task_hdrs}| {'pass  avg tok/s   tot s':<{SUM_W}} |")

    # Sub-header: column meaning
    sub_hdrs = "".join(f"| {'ok  tok/s  wall':<{CELL_W}} " for _ in tasks)
    print(f"| {'':<{model_w}} | {'est':^{SPD_W}} {sub_hdrs}| {'':<{SUM_W}} |")

    print(bar)

    for model in models:
        recs  = [idx.get((model, t)) for t in tasks]
        cells = "".join(f"| {cell(r)} " for r in recs)
        rank  = speed_rank[model]
        print(f"| {model:<{model_w}} | {rank:^{SPD_W}} {cells}| {summary(recs):<{SUM_W}} |")

    print(bar)


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 64)
    print("FAILURE DETAIL")
    print("=" * 64)

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    any_failures = False
    for model, recs in by_model.items():
        failures = [r for r in recs if not r["tests_pass"]]
        if not failures:
            continue
        any_failures = True
        counts: dict[str, int] = defaultdict(int)
        for r in failures:
            counts[r.get("error_kind") or "unknown"] += 1
        print(f"\nModel : {model}")
        for kind, count in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {count}")
            samples = [r for r in failures if r.get("error_kind") == kind][:1]
            for s in samples:
                detail = (s.get("error_detail") or "")[:120].replace("\n", " ")
                if detail:
                    print(f"    e.g. {detail}")

    if not any_failures:
        print("\nAll tasks passed.")
    print()
