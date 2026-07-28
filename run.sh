#!/usr/bin/env bash
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Console logging ───────────────────────────────────────────────────────────
# Skipped when called from compare.sh (BENCH_NO_LOG=1) to avoid double-logging.
if [[ "${BENCH_NO_LOG:-0}" -eq 0 ]]; then
    _LOG_DIR="$_SCRIPT_DIR/logs"
    mkdir -p "$_LOG_DIR"
    _log_num=0
    for _f in "$_LOG_DIR"/run-[0-9]*.log; do
        [[ -f "$_f" ]] || continue
        _n="${_f##*/run-}"; _n="${_n%.log}"
        [[ "$_n" =~ ^[0-9]+$ ]] && [[ "10#$_n" -gt "$_log_num" ]] && _log_num=$(( 10#$_n )) || true
    done
    _log_num=$(( _log_num + 1 ))
    _LOG_FILE="$_LOG_DIR/run-$(printf '%02d' "$_log_num").log"
    exec > >(tee "$_LOG_FILE") 2>&1
    ls -t "$_LOG_DIR"/run-[0-9]*.log 2>/dev/null | tail -n +11 | xargs -r rm -f
    ln -sf "$(basename "$_LOG_FILE")" "$_LOG_DIR/run-latest.log"
fi

_RUN_START=$(date +%s)
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"

VENV=".venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

pip install --quiet -r requirements.txt

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
    if [[ -f "$_HW_LOG" ]]; then
        python3 - "$_HW_LOG" <<'PYEOF'
import sys, re
from collections import defaultdict
core = defaultdict(list)
jct  = defaultdict(list)
n = 0
with open(sys.argv[1]) as fh:
    for line in fh:
        if not re.match(r'^\d{2}:\d{2}:\d{2}', line):
            continue
        n += 1
        for m in re.finditer(r'GPU(\d+)\[[^\]]+\]\s+(\d+)°C(?:\s+jct:(\d+)°C)?', line):
            idx = m.group(1)
            core[idx].append(float(m.group(2)))
            if m.group(3):
                jct[idx].append(float(m.group(3)))
if not core:
    sys.exit(0)
parts = []
for idx in sorted(core):
    v = core[idx]
    parts.append(f'GPU{idx} core {min(v):.0f}/{sum(v)/len(v):.0f}/{max(v):.0f}°C')
    if idx in jct:
        v = jct[idx]
        parts.append(f'GPU{idx} jct {min(v):.0f}/{sum(v)/len(v):.0f}/{max(v):.0f}°C')
print(f'[hwmonitor] temps (min/avg/max, {n} samples): ' + '  '.join(parts))
PYEOF
    fi
fi

_ELAPSED=$(( $(date +%s) - _RUN_START ))
printf "Total runtime: %02d:%02d:%02d\n" $((_ELAPSED/3600)) $(((_ELAPSED%3600)/60)) $((_ELAPSED%60))

exit "$_BENCH_EXIT"
