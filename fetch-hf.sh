#!/usr/bin/env bash
set -euo pipefail
# Download GGUF files from HuggingFace Hub.
# Requires $LLAMA_MODELS_DIR to be set.
# Uses the Python venv (run ./run.sh once first to create it).
#
# Usage:
#   export LLAMA_MODELS_DIR=/path/to/gguf
#   ./fetch-hf.sh                          # download all models with hf: fields
#   ./fetch-hf.sh models/default.txt       # specific model file
#   ./fetch-hf.sh --models qwen3.5:35b     # specific model(s) only
#   ./fetch-hf.sh --dry-run                # preview without downloading

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "Virtual environment not found at $VENV"
    echo "Run ./run.sh once first to create it, or: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source "$VENV/bin/activate"
python3 "$SCRIPT_DIR/fetch-hf.py" "$@"
