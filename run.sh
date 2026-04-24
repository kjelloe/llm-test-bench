#!/usr/bin/env bash
set -euo pipefail

VENV=".venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

pip install --quiet -r requirements.txt

python3 bench.py "$@"
