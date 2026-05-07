#!/usr/bin/env bash
set -euo pipefail
# Compare two bench result JSON files — speed summary + full task table.
#
# Usage:
#   ./compare-results.sh output/results-compare.json output/results-compare-ls.json
#   ./compare-results.sh output/results-default.json output/results-default-ls.json

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "Virtual environment not found. Run ./run.sh once first to create it."
    exit 1
fi

source "$VENV/bin/activate"
python3 "$SCRIPT_DIR/compare-results.py" "$@"
