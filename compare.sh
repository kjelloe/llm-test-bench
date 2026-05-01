#!/usr/bin/env bash
set -euo pipefail
#
# Usage:
#   ./compare.sh                          run the 'default' model set
#   ./compare.sh <set-name>               run a named set from models/<set-name>.txt
#   ./compare.sh --models m1 m2 ...       ad-hoc model list
#   ./compare.sh --list                   list available model sets and exit
#
# Any remaining flags are forwarded to bench.py, e.g.:
#   ./compare.sh extended --num-ctx 16384
#   ./compare.sh --models qwen2.5-coder:14b --tasks python_safe_div
#   ./compare.sh full --tasks node_slugify python_safe_div

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/models"
STATS_FILE="$SCRIPT_DIR/compare-history.json"
MODEL_TIMEOUT=900
NUM_PREDICT=2400

# ── Parse arguments ────────────────────────────────────────────────────────────
MODELS=()
BENCH_ARGS=()
SET_NAME=""
SET_LABEL=""

if [[ $# -eq 0 ]]; then
    SET_NAME="default"

elif [[ "$1" == "--list" ]]; then
    echo "Available model sets (models/*.txt):"
    for _f in "$MODELS_DIR"/*.txt; do
        [[ -f "$_f" ]] || continue
        _name="$(basename "$_f" .txt)"
        _count=$(grep -v '^\s*#' "$_f" | grep -v '^\s*$' | wc -l | tr -d ' ')
        printf "  %-20s  %s models\n" "$_name" "$_count"
    done
    exit 0

elif [[ "$1" == "--models" ]]; then
    shift
    while [[ $# -gt 0 && "$1" != --* ]]; do
        MODELS+=("$1")
        shift
    done
    BENCH_ARGS=("$@")
    SET_LABEL="ad-hoc"

elif [[ "$1" != --* ]]; then
    SET_NAME="$1"
    shift
    BENCH_ARGS=("$@")

else
    # Flags only — use default set
    SET_NAME="default"
    BENCH_ARGS=("$@")
fi

# ── Load model set from file ──────────────────────────────────────────────────
if [[ -n "$SET_NAME" ]]; then
    SET_FILE="$MODELS_DIR/${SET_NAME}.txt"
    if [[ ! -f "$SET_FILE" ]]; then
        echo "Error: model set '$SET_NAME' not found at $SET_FILE"
        echo ""
        echo "Available sets:"
        for _f in "$MODELS_DIR"/*.txt; do
            [[ -f "$_f" ]] && printf "  %s\n" "$(basename "$_f" .txt)"
        done
        echo ""
        echo "Run './compare.sh --list' for details, or './compare.sh --models m1 m2' for ad-hoc."
        exit 1
    fi
    while IFS= read -r _line || [[ -n "$_line" ]]; do
        _line="${_line%%#*}"           # strip inline comment
        _line="${_line//[[:space:]]/}" # strip whitespace (model names have none)
        [[ -n "$_line" ]] && MODELS+=("$_line")
    done < "$SET_FILE"
    if [[ ${#MODELS[@]} -eq 0 ]]; then
        echo "Error: model set '$SET_NAME' contains no models ($SET_FILE)"
        exit 1
    fi
    SET_LABEL="set '$SET_NAME'"
fi

# ── Determine output file ─────────────────────────────────────────────────────
# Default: results-<set-name>.json, or results-compare.json for ad-hoc.
# If --out appears in BENCH_ARGS, extract and use it (keeps $OUT consistent for history).
if [[ -n "$SET_NAME" && "$SET_NAME" != "default" ]]; then
    OUT="$SCRIPT_DIR/results-${SET_NAME}.json"
else
    OUT="$SCRIPT_DIR/results-compare.json"
fi

_clean=()
_skip=false
for _arg in "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}"; do
    if $_skip; then OUT="$_arg"; _skip=false
    elif [[ "$_arg" == "--out" ]]; then _skip=true
    else _clean+=("$_arg")
    fi
done
BENCH_ARGS=("${_clean[@]+"${_clean[@]}"}")
unset _clean _skip _arg _line _f _name _count

# ── Header ────────────────────────────────────────────────────────────────────
NUM_MODELS=${#MODELS[@]}
NUM_TASKS=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from tasks import BUILTIN_TASKS
print(len(BUILTIN_TASKS))
" 2>/dev/null || echo 11)
MAX_RUNTIME=$(( MODEL_TIMEOUT * NUM_MODELS * NUM_TASKS ))

echo "════════════════════════════════════════════════════════════"
echo "  ollama-code-bench — $SET_LABEL  (${NUM_MODELS} models × ${NUM_TASKS} tasks)"
echo "════════════════════════════════════════════════════════════"
printf "  Models (%d):\n" "$NUM_MODELS"
for i in "${!MODELS[@]}"; do
  printf "    %d. %s\n" "$((i+1))" "${MODELS[$i]}"
done
printf "  Tasks       : %d\n" "$NUM_TASKS"
printf "  Output      : %s\n" "$(basename "$OUT")"
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
            print(f"    {model:<40s} last {e['passes']}/{e['total_tasks']}  {e['avg_tok_per_s']} tok/s  [{e['timestamp'][:10]}]")
        else:
            print(f"    {model:<40s} no prior data")
    archived = [m for m in mh if m not in current_models]
    if archived:
        print("  Archived models (not in current run):")
        for model in archived:
            e = mh[model][-1]
            print(f"    {model:<40s} last {e['passes']}/{e['total_tasks']}  {e['avg_tok_per_s']} tok/s  [{e['timestamp'][:10]}]")
PYEOF
else
  echo "  No run history found."
fi
echo "════════════════════════════════════════════════════════════"
echo

# ── Run ───────────────────────────────────────────────────────────────────────
"$SCRIPT_DIR/run.sh" \
  --models "${MODELS[@]}" \
  --num-predict "$NUM_PREDICT" \
  --model-timeout "$MODEL_TIMEOUT" \
  --warmup \
  --out "$OUT" \
  "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}"

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
