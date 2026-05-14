#!/usr/bin/env bash
set -euo pipefail
# Scout HuggingFace Hub for new GGUF models suitable for coding + context benchmarks.
# Saves state to output/hf-scout-state.json; on re-runs shows only what changed
# (new repos, updated file lists, repos that disappeared).
#
# Usage:
#   ./scout-hf.sh                          # run with default queries
#   ./scout-hf.sh --no-save               # dry-run, do not update state
#   ./scout-hf.sh --show-all              # also print full repo list on re-runs
#   ./scout-hf.sh --limit 12             # more repos per query (default: 8)
#   ./scout-hf.sh --token hf_xxx         # explicit token (or set HF_TOKEN env var)
#   ./scout-hf.sh --queries "qwen3" "llama3 instruct"  # custom queries
#
# Auth: set HF_TOKEN in your environment to avoid rate limits.
#   A free HuggingFace account token is sufficient.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "Virtual environment not found at $VENV"
    echo "Run ./run.sh once first to create it."
    exit 1
fi

source "$VENV/bin/activate"
python3 "$SCRIPT_DIR/lib/scout_hf.py" "$@"
