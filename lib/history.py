#!/usr/bin/env python3
"""Manage compare-history.json: print header stats and save run summaries."""

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path


def cmd_show(stats_file: str, current_models: list[str]) -> None:
    history_path = Path(stats_file)
    if not history_path.exists():
        print("  No run history found.")
        return
    history = json.loads(history_path.read_text())
    runs = history.get("runs", [])
    if runs:
        last = runs[-1]
        w = last.get("total_wall_s", 0)
        ts = last.get("timestamp", "?")
        o = last.get("overall", {})
        passed, pairs = o.get("passes", "?"), o.get("pairs", "?")
        m, s = int(w // 60), int(w % 60)
        print(f"  Last run    : {ts}  {passed}/{pairs} passed  ({m}m {s}s wall)")
        hw = last.get("hardware")
        if hw:
            from lib.hw_snapshot import hw_summary
            print(f"  Hardware    : {hw_summary(hw)}")
    mh = history.get("model_history", {})
    if mh:
        print("  Model history:")
        for model in current_models:
            entries = mh.get(model, [])
            if entries:
                e = entries[-1]
                print(f"    {model:<40s} last {e['passes']}/{e['total_tasks']}  {e['avg_tok_per_s']} tok/s  [{e['timestamp'][:10]}]")
            else:
                print(f"    {model:<40s} no prior data")
        archived = [mdl for mdl in mh if mdl not in current_models]
        if archived:
            print("  Archived models (not in current run):")
            for model in archived:
                e = mh[model][-1]
                print(f"    {model:<40s} last {e['passes']}/{e['total_tasks']}  {e['avg_tok_per_s']} tok/s  [{e['timestamp'][:10]}]")


def cmd_save(results_file: str, history_file: str) -> None:
    results_path, history_path = Path(results_file), Path(history_file)
    if not results_path.exists():
        return

    raw = json.loads(results_path.read_text())
    hardware: dict | None = None
    if isinstance(raw, dict):
        results = raw["results"]
        hardware = raw.get("hardware")
    else:
        results = raw
    models = list(dict.fromkeys(r["model"] for r in results))
    tasks  = list(dict.fromkeys(r["task"]  for r in results))
    idx    = {(r["model"], r["task"]): r for r in results}

    total_wall   = sum(r.get("wall_s", 0) for r in results)
    total_passes = sum(1 for r in results if r.get("tests_pass"))

    tok_order = sorted(models, key=lambda mdl: -(
        sum(idx[(mdl, t)]["tok_per_s"] for t in tasks if (mdl, t) in idx and idx[(mdl, t)].get("tok_per_s", 0) > 0)
        / max(1, sum(1 for t in tasks if (mdl, t) in idx and idx[(mdl, t)].get("tok_per_s", 0) > 0))
    ))
    actual_rank = {mdl: i + 1 for i, mdl in enumerate(tok_order)}

    per_model = []
    for rank, model in enumerate(models, 1):
        recs   = [idx.get((model, t)) for t in tasks]
        passes = sum(1 for r in recs if r and r.get("tests_pass"))
        toks   = [r["tok_per_s"] for r in recs if r and r.get("tok_per_s", 0) > 0]
        errs   = defaultdict(int)
        for r in recs:
            if r and not r.get("tests_pass") and r.get("error_kind"):
                errs[r["error_kind"]] += 1
        per_task = {}
        for t in tasks:
            r = idx.get((model, t))
            if r:
                entry: dict = {"pass": r.get("tests_pass", False),
                               "tok_per_s": r.get("tok_per_s", 0),
                               "wall_s": r.get("wall_s", 0)}
                if not r.get("tests_pass") and r.get("error_kind"):
                    entry["error_kind"] = r["error_kind"]
                per_task[t] = entry
        per_model.append({
            "model":           model,
            "assumed_rank":    rank,
            "actual_tok_rank": actual_rank[model],
            "passes":          passes,
            "fails":           len(tasks) - passes,
            "avg_tok_per_s":   round(sum(toks) / len(toks), 1) if toks else 0.0,
            "total_wall_s":    round(sum(r["wall_s"] for r in recs if r), 1),
            "error_kinds":     dict(errs),
            "per_task":        per_task,
        })

    run = {
        "timestamp":    datetime.datetime.now().isoformat(timespec="seconds"),
        "total_wall_s": round(total_wall, 1),
        "models":       models,
        "tasks":        tasks,
        "overall":      {"pairs": len(results), "passes": total_passes,
                         "fails": len(results) - total_passes},
        "per_model":    per_model,
        "hardware":     hardware,
    }

    history = (json.loads(history_path.read_text())
               if history_path.exists() else {"runs": [], "model_history": {}})
    history.setdefault("model_history", {})
    history["runs"].append(run)
    history["runs"] = history["runs"][-10:]

    mh = history["model_history"]
    for m in per_model:
        entry = {
            "timestamp":     run["timestamp"],
            "passes":        m["passes"],
            "total_tasks":   len(tasks),
            "avg_tok_per_s": m["avg_tok_per_s"],
            "total_wall_s":  m["total_wall_s"],
            "per_task":      m["per_task"],
        }
        mh.setdefault(m["model"], []).append(entry)
        mh[m["model"]] = mh[m["model"]][-10:]

    history_path.write_text(json.dumps(history, indent=2))
    print(f"\nHistory saved → {history_path}  ({total_passes}/{len(results)} passed, total wall: {total_wall:.0f}s)")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("show", "save"):
        print("Usage: history.py show <stats_file> <model> ... | history.py save <results_file> <stats_file>")
        sys.exit(1)
    if sys.argv[1] == "show":
        cmd_show(sys.argv[2], sys.argv[3:])
    else:
        cmd_save(sys.argv[2], sys.argv[3])
