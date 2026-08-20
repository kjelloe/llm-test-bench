#!/usr/bin/env bash
set -euo pipefail
# Compare two bench result JSON files — speed summary + full task table.
#
# Usage:
#   ./compare-results.sh output/results-compare.json output/results-compare-ls.json
#   ./compare-results.sh output/results-default.json output/results-default-ls.json

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -eq 0 ]]; then
    cat <<'EOF'
Usage: ./compare-results.sh FILE1 FILE2

Compare two bench result JSON files side by side — speed summary + full task table.
Typically used to compare ollama vs llama-server runs for the same model set.

  FILE1   First results file  (e.g. output/results-compare.json)
  FILE2   Second results file (e.g. output/results-compare-ls.json)
  -h, --help   Show this help and exit

Examples:
  ./compare-results.sh output/results-compare.json output/results-compare-ls.json
  ./compare-results.sh output/results-default.json output/results-default-ls.json
EOF
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "Virtual environment not found. Run ./run.sh once first to create it."
    exit 1
fi

source "$VENV/bin/activate"
python3 "$SCRIPT_DIR/lib/compare_results.py" "$@"
