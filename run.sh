#!/usr/bin/env bash
set -euo pipefail

echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"

VENV=".venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

pip install --quiet -r requirements.txt

# ── GPU mode ────────────────────────────────────────────────────────────────
# Source .gpu-mode if present (written by gpu-mode.sh).
# single-GPU mode: export CUDA_VISIBLE_DEVICES (inherited by all backends) and
# pass --single-gpu so bench.py can strip tensor_split for llama-server.
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_GPU_ARGS=()
if [[ -f "$_SCRIPT_DIR/.gpu-mode" ]]; then
    # shellcheck source=/dev/null
    source "$_SCRIPT_DIR/.gpu-mode"
    if [[ "${GPU_SINGLE_INDEX:-"-1"}" != "-1" ]]; then
        export CUDA_VISIBLE_DEVICES="${GPU_SINGLE_INDEX}"
        # Only inject if not already passed by the caller
        if [[ ! " $* " =~ " --single-gpu " ]]; then
            _GPU_ARGS=(--single-gpu "${GPU_SINGLE_INDEX}")
        fi
    fi
fi

python3 bench.py "${_GPU_ARGS[@]+"${_GPU_ARGS[@]}"}" "$@"
