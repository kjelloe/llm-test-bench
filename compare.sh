#!/usr/bin/env bash
set -euo pipefail

# Run the full benchmark across all candidate models and print a comparison table.
#
# --num-predict 1200  : thinking models need extra tokens for reasoning before
#                       they emit the BEGIN_FILE block; 400 is too few.
# --model-timeout 900 : 120B models on RAM (qwen3.5:122b, gpt-oss:120b) can run at
#                       1–2 tok/s; at 1200 tokens that's up to 1200s worst-case.
#                       900s covers most runs without waiting indefinitely on hangs.
#
# Extra flags (e.g. --tasks python_safe_div --num-ctx 16384) are forwarded to bench.py.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=bench-models.sh
source "$SCRIPT_DIR/bench-models.sh"

MODEL_TIMEOUT=900
NUM_PREDICT=1200
OUT="$SCRIPT_DIR/results-compare.json"
STATS_FILE="$SCRIPT_DIR/compare-history.json"

# ── Header ────────────────────────────────────────────────────────────────────
NUM_MODELS=${#MODELS[@]}
NUM_TASKS=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from tasks import BUILTIN_TASKS
print(len(BUILTIN_TASKS))
" 2>/dev/null || echo 3)
MAX_RUNTIME=$(( MODEL_TIMEOUT * NUM_MODELS * NUM_TASKS ))

echo "════════════════════════════════════════════════════════════"
echo "  ollama-code-bench — compare"
echo "════════════════════════════════════════════════════════════"
printf "  Models (%d, assumed fastest → slowest):\n" "$NUM_MODELS"
for i in "${!MODELS[@]}"; do
  printf "    %d. %s\n" "$((i+1))" "${MODELS[$i]}"
done
printf "  Tasks       : %d\n" "$NUM_TASKS"
printf "  Max runtime : %ds  (%ds timeout × %d models × %d tasks)\n" \
  "$MAX_RUNTIME" "$MODEL_TIMEOUT" "$NUM_MODELS" "$NUM_TASKS"

if [[ -f "$STATS_FILE" ]]; then
  python3 - "$STATS_FILE" <<'PYEOF'
import json, sys
history = json.load(open(sys.argv[1]))
runs = history.get("runs", [])
if runs:
    last = runs[-1]
    w  = last.get("total_wall_s", 0)
    ts = last.get("last_run_timestamp", last.get("timestamp", "?"))
    o  = last.get("overall", {})
    passed, pairs = o.get("passes", "?"), o.get("pairs", "?")
    m, s = int(w // 60), int(w % 60)
    print(f"  Est. runtime: {w:.0f}s ({m}m {s}s)  [last run: {ts}, result: {passed}/{pairs} passed]")
PYEOF
else
  echo "  Est. runtime: unknown  (no previous run recorded)"
fi
echo "════════════════════════════════════════════════════════════"
echo

# ── Run ───────────────────────────────────────────────────────────────────────
"$SCRIPT_DIR/run.sh" \
  --models "${MODELS[@]}" \
  --num-predict "$NUM_PREDICT" \
  --model-timeout "$MODEL_TIMEOUT" \
  --out "$OUT" \
  "$@"

# ── Save run to history file ──────────────────────────────────────────────────
python3 - "$OUT" "$STATS_FILE" <<'PYEOF'
import json, sys, datetime
from collections import defaultdict
from pathlib import Path

results_path, history_path = Path(sys.argv[1]), Path(sys.argv[2])
if not results_path.exists():
    sys.exit()

results = json.loads(results_path.read_text())
models  = list(dict.fromkeys(r["model"] for r in results))
tasks   = list(dict.fromkeys(r["task"]  for r in results))
idx     = {(r["model"], r["task"]): r for r in results}

total_wall   = sum(r.get("wall_s", 0) for r in results)
total_passes = sum(1 for r in results if r.get("tests_pass"))

# Compute actual tok/s rank (1 = fastest measured)
tok_order = sorted(models, key=lambda m: -sum(
    idx[(m, t)]["tok_per_s"] for t in tasks if (m, t) in idx and idx[(m,t)].get("tok_per_s",0) > 0
) / max(1, sum(1 for t in tasks if (m,t) in idx and idx[(m,t)].get("tok_per_s",0) > 0)))
actual_rank = {m: i+1 for i, m in enumerate(tok_order)}

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
            entry = {"pass": r.get("tests_pass", False),
                     "tok_per_s": r.get("tok_per_s", 0),
                     "wall_s": r.get("wall_s", 0)}
            if not r.get("tests_pass") and r.get("error_kind"):
                entry["error_kind"] = r["error_kind"]
            per_task[t] = entry
    per_model.append({
        "model":         model,
        "assumed_rank":  rank,
        "actual_tok_rank": actual_rank[model],
        "passes":        passes,
        "fails":        len(tasks) - passes,
        "avg_tok_per_s": round(sum(toks) / len(toks), 1) if toks else 0.0,
        "total_wall_s": round(sum(r["wall_s"] for r in recs if r), 1),
        "error_kinds":  dict(errs),
        "per_task":     per_task,
    })

run = {
    "timestamp":    datetime.datetime.now().isoformat(timespec="seconds"),
    "total_wall_s": round(total_wall, 1),
    "models":       models,
    "tasks":        tasks,
    "overall":      {"pairs": len(results), "passes": total_passes,
                     "fails": len(results) - total_passes},
    "per_model":    per_model,
}

history = json.loads(history_path.read_text()) if history_path.exists() else {"runs": []}
history["runs"].append(run)
history["runs"] = history["runs"][-10:]  # keep last 10 runs
history_path.write_text(json.dumps(history, indent=2))
print(f"\nHistory saved → {history_path}  ({total_passes}/{len(results)} passed, total wall: {total_wall:.0f}s)")
PYEOF
