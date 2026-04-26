#!/usr/bin/env bash
set -euo pipefail

# Extended benchmark — all 8 models that have been evaluated, all 10 tasks.
# Writes to results-extended.json and appends to compare-history.json.
#
# Excluded:
#   llama3.3:70b-instruct-q4_K_M — 1.6 tok/s RAM-bound; times out on thinking tasks
#   phi4-reasoning:14b            — systematic dotnet_sas format failure
#   deepcoder:14b                 — burns all tokens on thinking, needs 4800+ to be useful
#
# Estimated runtime: ~2.5–4 hours depending on GPU load.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODELS=(
  "gpt-oss:20b"          # ~82 tok/s  thinking, GPU-resident
  "qwen2.5-coder:14b"    # ~40 tok/s  GPU
  "qwen3-coder:30b"      # ~36 tok/s  GPU
  "gemma4:26b"           # ~28 tok/s  GPU, partial offload
  "codestral:22b"        # ~18 tok/s  GPU
  "devstral-small-2"     # ~16 tok/s  GPU
  "qwen3.5:35b"          # ~16 tok/s  thinking, partial RAM
  "gpt-oss:120b"         # ~11 tok/s  thinking, RAM-bound
)

MODEL_TIMEOUT=900
NUM_PREDICT=2400
OUT="$SCRIPT_DIR/results-extended.json"
STATS_FILE="$SCRIPT_DIR/compare-history.json"

NUM_MODELS=${#MODELS[@]}
NUM_TASKS=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from tasks import BUILTIN_TASKS
print(len(BUILTIN_TASKS))
" 2>/dev/null || echo 10)
MAX_RUNTIME=$(( MODEL_TIMEOUT * NUM_MODELS * NUM_TASKS ))

echo "════════════════════════════════════════════════════════════"
echo "  ollama-code-bench — extended compare  (8 models × ${NUM_TASKS} tasks)"
echo "════════════════════════════════════════════════════════════"
printf "  Models (%d, fastest → slowest):\n" "$NUM_MODELS"
for i in "${!MODELS[@]}"; do
  printf "    %d. %s\n" "$((i+1))" "${MODELS[$i]}"
done
printf "  Tasks       : %d\n" "$NUM_TASKS"
printf "  Max runtime : %ds  (%ds timeout × %d models × %d tasks)\n" \
  "$MAX_RUNTIME" "$MODEL_TIMEOUT" "$NUM_MODELS" "$NUM_TASKS"

if [[ -f "$STATS_FILE" ]]; then
  python3 - "$STATS_FILE" "${MODELS[@]}" <<'PYEOF'
import json, sys
history = json.load(open(sys.argv[1]))
current_models = sys.argv[2:]
runs = history.get("runs", [])
if runs:
    last = runs[-1]
    w  = last.get("total_wall_s", 0)
    ts = last.get("timestamp", "?")
    o  = last.get("overall", {})
    passed, pairs = o.get("passes", "?"), o.get("pairs", "?")
    m, s = int(w // 60), int(w % 60)
    print(f"  Last run    : {ts}  {passed}/{pairs} passed  ({m}m {s}s wall)")
mh = history.get("model_history", {})
if mh:
    print("  Model history:")
    for model in current_models:
        entries = mh.get(model, [])
        if entries:
            e = entries[-1]
            print(f"    {model:<38s} last {e['passes']}/{e['total_tasks']}  {e['avg_tok_per_s']} tok/s  [{e['timestamp'][:10]}]")
        else:
            print(f"    {model:<38s} no prior data")
PYEOF
else
  echo "  Est. runtime: unknown  (no previous run recorded)"
fi
echo "════════════════════════════════════════════════════════════"
echo

"$SCRIPT_DIR/run.sh" \
  --models "${MODELS[@]}" \
  --num-predict "$NUM_PREDICT" \
  --model-timeout "$MODEL_TIMEOUT" \
  --warmup \
  --out "$OUT" \
  "$@"

# Append to shared history file
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
        "model":            model,
        "assumed_rank":     rank,
        "actual_tok_rank":  actual_rank[model],
        "passes":           passes,
        "fails":            len(tasks) - passes,
        "avg_tok_per_s":    round(sum(toks) / len(toks), 1) if toks else 0.0,
        "total_wall_s":     round(sum(r["wall_s"] for r in recs if r), 1),
        "error_kinds":      dict(errs),
        "per_task":         per_task,
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

history = json.loads(history_path.read_text()) if history_path.exists() else {"runs": [], "model_history": {}}
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
PYEOF
