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
STATS_FILE="$SCRIPT_DIR/output/compare-history.json"
MODEL_TIMEOUT=1200
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
        _line="${_line#"${_line%%[! ]*}"}"  # strip leading whitespace
        [[ -z "$_line" ]] && continue
        _model="${_line%% *}"          # first field only (ollama name; remaining fields are GGUF/params)
        MODELS+=("$_model")
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
    OUT="$SCRIPT_DIR/output/results-${SET_NAME}.json"
else
    OUT="$SCRIPT_DIR/output/results-compare.json"
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
from lib.tasks import BUILTIN_TASKS
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

python3 "$SCRIPT_DIR/lib/history.py" show "$STATS_FILE" "${MODELS[@]}"
echo "════════════════════════════════════════════════════════════"
echo

# ── Run ───────────────────────────────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/output"

# Build model-file arg: pass the set file when using a named set so bench.py
# can resolve GGUF filenames for --backend llama-server.
_MODEL_FILE_ARGS=()
if [[ -n "${SET_FILE:-}" ]]; then
    _MODEL_FILE_ARGS=(--model-file "$SET_FILE")
fi

"$SCRIPT_DIR/run.sh" \
  --models "${MODELS[@]}" \
  "${_MODEL_FILE_ARGS[@]+"${_MODEL_FILE_ARGS[@]}"}" \
  --num-predict "$NUM_PREDICT" \
  --model-timeout "$MODEL_TIMEOUT" \
  --warmup \
  --out "$OUT" \
  "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}"

# ── Save run to history file ──────────────────────────────────────────────────
python3 "$SCRIPT_DIR/lib/history.py" save "$OUT" "$STATS_FILE"
