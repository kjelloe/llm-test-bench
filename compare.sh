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
d = json.load(open(sys.argv[1]))
w = d.get("last_run_wall_s", 0)
ts = d.get("last_run_timestamp", "?")
m, s = int(w // 60), int(w % 60)
print(f"  Est. runtime: {w:.0f}s ({m}m {s}s)  [last run: {ts}]")
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

# ── Save stats for next run's estimated runtime ───────────────────────────────
python3 - "$OUT" "$STATS_FILE" <<'PYEOF'
import json, sys, datetime
from pathlib import Path

results_path, stats_path = Path(sys.argv[1]), Path(sys.argv[2])
if not results_path.exists():
    sys.exit()

results = json.loads(results_path.read_text())
total_wall = sum(r.get("wall_s", 0) for r in results)

stats = {
    "last_run_wall_s":   round(total_wall, 1),
    "last_run_timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    "last_run_models":   list(dict.fromkeys(r["model"] for r in results)),
    "last_run_tasks":    list(dict.fromkeys(r["task"]  for r in results)),
}
Path(stats_path).write_text(json.dumps(stats, indent=2))
print(f"Stats saved → {stats_path}  (total wall: {total_wall:.0f}s)")
PYEOF
