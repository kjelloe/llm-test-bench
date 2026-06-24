#!/usr/bin/env bash
set -euo pipefail

_RUN_START=$(date +%s)
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"

VENV=".venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

pip install --quiet -r requirements.txt

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Strip --no-hwmonitor before forwarding args to bench.py ─────────────────
_NO_HWMONITOR=0
_PASSTHROUGH=()
for _arg in "$@"; do
    if [[ "$_arg" == "--no-hwmonitor" ]]; then
        _NO_HWMONITOR=1
    else
        _PASSTHROUGH+=("$_arg")
    fi
done
set -- "${_PASSTHROUGH[@]+"${_PASSTHROUGH[@]}"}"

# ── GPU mode ─────────────────────────────────────────────────────────────────
# Source .gpu-mode if present (written by gpu-mode.sh).
# single-GPU mode: export CUDA_VISIBLE_DEVICES (inherited by all backends) and
# pass --single-gpu so bench.py can strip tensor_split for llama-server.
_GPU_ARGS=()
if [[ -f "$_SCRIPT_DIR/.gpu-mode" ]]; then
    # shellcheck source=/dev/null
    source "$_SCRIPT_DIR/.gpu-mode"
    if [[ "${GPU_SINGLE_INDEX:-"-1"}" != "-1" ]]; then
        export CUDA_VISIBLE_DEVICES="${GPU_SINGLE_INDEX}"
        if [[ ! " $* " =~ " --single-gpu " ]]; then
            _GPU_ARGS=(--single-gpu "${GPU_SINGLE_INDEX}")
        fi
    fi
fi

# ── Launch bench.py in background ────────────────────────────────────────────
python3 bench.py "${_GPU_ARGS[@]+"${_GPU_ARGS[@]}"}" "$@" &
_BENCH_PID=$!

# ── Start hwmonitor in background ────────────────────────────────────────────
# Quiet mode: data lines go to log only; WARN/CRIT/OK appear on stderr.
# Skipped if --no-hwmonitor passed or hwmonitor.py not found.
_HW_PID=""
if [[ "$_NO_HWMONITOR" -eq 0 && -x "$_SCRIPT_DIR/hwmonitor/hwmonitor.py" ]]; then
    mkdir -p "$_SCRIPT_DIR/output"
    _HW_LOG="$_SCRIPT_DIR/output/hwmonitor-$(date '+%Y%m%d-%H%M%S').log"
    python3 "$_SCRIPT_DIR/hwmonitor/hwmonitor.py" \
        --pid "$_BENCH_PID" \
        --quiet \
        --log "$_HW_LOG" &
    _HW_PID=$!
    echo "[hwmonitor] started — log: $_HW_LOG"
fi

# ── Wait for bench.py; preserve its exit code ────────────────────────────────
wait "$_BENCH_PID" && _BENCH_EXIT=0 || _BENCH_EXIT=$?

# ── Stop hwmonitor ───────────────────────────────────────────────────────────
if [[ -n "$_HW_PID" ]]; then
    kill "$_HW_PID" 2>/dev/null || true
    wait "$_HW_PID" 2>/dev/null || true
    echo "[hwmonitor] stopped"
fi

_ELAPSED=$(( $(date +%s) - _RUN_START ))
printf "Total runtime: %02d:%02d:%02d\n" $((_ELAPSED/3600)) $(((_ELAPSED%3600)/60)) $((_ELAPSED%60))

exit "$_BENCH_EXIT"
