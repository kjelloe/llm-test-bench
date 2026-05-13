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
#   ./compare.sh --set-power-limit 350    enforce GPU wattage cap before benchmarking
#
# GPU power limit:
#   Power limits reset on reboot. Set POWER_LIMIT below to enforce a cap at the
#   start of every run (requires sudo). Leave empty to leave the limit unchanged.
#   Alternatively pass --set-power-limit WATTS on the command line.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/models"
STATS_FILE="$SCRIPT_DIR/output/compare-history.json"
MODEL_TIMEOUT=1200
NUM_PREDICT=8000
STARTUP_TIMEOUT=600
POWER_LIMIT=350  # set GPU power limit (W) before run; requires sudo; empty = no change

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
# Default: results-<set-name>[-<backend>].json, or results-compare[-<backend>].json.
# Extract --backend and --out from BENCH_ARGS so we can use them for naming.
BACKEND="${BENCH_BACKEND:-ollama}"
_clean=()
_skip_out=false
_skip_be=false
for _arg in "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}"; do
    if   $_skip_out; then OUT_OVERRIDE="$_arg"; _skip_out=false
    elif $_skip_be;  then BACKEND="$_arg";      _skip_be=false; _clean+=("--backend" "$_arg")
    elif [[ "$_arg" == "--out"     ]]; then _skip_out=true
    elif [[ "$_arg" == "--backend" ]]; then _skip_be=true
    else _clean+=("$_arg")
    fi
done
BENCH_ARGS=("${_clean[@]+"${_clean[@]}"}")
unset _clean _skip_out _skip_be _arg _line _f _name _count

# Abbreviate backend for filenames: llama-server → ls
BACKEND_SUFFIX=""
if [[ "$BACKEND" != "ollama" ]]; then
    BACKEND_SUFFIX="-${BACKEND/llama-server/ls}"
fi

if [[ -n "${OUT_OVERRIDE:-}" ]]; then
    OUT="$OUT_OVERRIDE"
elif [[ -n "$SET_NAME" && "$SET_NAME" != "default" ]]; then
    OUT="$SCRIPT_DIR/output/results-${SET_NAME}${BACKEND_SUFFIX}.json"
else
    OUT="$SCRIPT_DIR/output/results-compare${BACKEND_SUFFIX}.json"
fi

# ── Resume check ─────────────────────────────────────────────────────────────
# Checkpoint dir is named after the output file (backend suffix included), so
# ollama and llama-server checkpoints never collide.
CHECKPOINT_DIR="$SCRIPT_DIR/output/.resume/$(basename "$OUT" .json)"
CHECKPOINT_ARGS=(--checkpoint-dir "$CHECKPOINT_DIR")

if [[ -d "$CHECKPOINT_DIR" ]]; then
    _ckpt_files=("$CHECKPOINT_DIR"/*.json)
    # bash glob returns the literal pattern when no files match
    if [[ -f "${_ckpt_files[0]:-}" ]]; then
        _ckpt_count=${#_ckpt_files[@]}
        echo "  Checkpoint found — $_ckpt_count model(s) already completed:"
        for _f in "${_ckpt_files[@]}"; do
            _mname=$(python3 -c "
import json, sys
try:
    d=json.load(open('$_f')); print(d[0]['model'] if d else '?')
except: print('?')
" 2>/dev/null)
            printf "    [done] %s\n" "$_mname"
        done
        printf "  Resume from checkpoint? [Y/n] "
        read -r _resume_answer </dev/tty || _resume_answer="y"
        if [[ "${_resume_answer:-y}" =~ ^[Nn] ]]; then
            echo "  Starting fresh — removing checkpoint."
            rm -rf "$CHECKPOINT_DIR"
        else
            echo "  Resuming."
        fi
        unset _resume_answer _mname _f _ckpt_count
    fi
    unset _ckpt_files
fi

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
# Look up HF repos from the model file when available
_hf_lookup=""
if [[ -n "${SET_FILE:-}" ]]; then
  _hf_lookup=$(python3 - <<PYEOF 2>/dev/null
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from lib.model_config import load_model_file
for c in load_model_file('$SET_FILE'):
    print(f"{c.ollama_name}\t{c.hf_repo or ''}")
PYEOF
)
fi
_name_w=0
for _m in "${MODELS[@]}"; do [[ ${#_m} -gt $_name_w ]] && _name_w=${#_m}; done
for i in "${!MODELS[@]}"; do
  _name="${MODELS[$i]}"
  _hf=$(printf '%s' "$_hf_lookup" | awk -F'\t' -v n="$_name" '$1==n{print $2; exit}')
  if [[ -n "$_hf" ]]; then
    printf "    %d. %-*s  hf:%s\n" "$((i+1))" "$_name_w" "$_name" "$_hf"
  else
    printf "    %d. %s\n" "$((i+1))" "$_name"
  fi
done
unset _hf_lookup _name_w _name _hf _m
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

_POWER_ARGS=()
[[ -n "$POWER_LIMIT" ]] && _POWER_ARGS=(--set-power-limit "$POWER_LIMIT")

"$SCRIPT_DIR/run.sh" \
  --models "${MODELS[@]}" \
  "${_MODEL_FILE_ARGS[@]+"${_MODEL_FILE_ARGS[@]}"}" \
  --num-predict "$NUM_PREDICT" \
  --model-timeout "$MODEL_TIMEOUT" \
  --startup-timeout "$STARTUP_TIMEOUT" \
  --warmup \
  --out "$OUT" \
  "${CHECKPOINT_ARGS[@]}" \
  "${_POWER_ARGS[@]+"${_POWER_ARGS[@]}"}" \
  "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}"

# ── Clean up checkpoint on successful completion ───────────────────────────────
[[ -d "$CHECKPOINT_DIR" ]] && rm -rf "$CHECKPOINT_DIR"

# ── Save run to history file ──────────────────────────────────────────────────
python3 "$SCRIPT_DIR/lib/history.py" save "$OUT" "$STATS_FILE"
