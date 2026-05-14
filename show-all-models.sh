#!/usr/bin/env bash
set -euo pipefail

OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

if ! curl -sf --max-time 3 "$OLLAMA_URL" &>/dev/null; then
  echo "ERROR: Ollama not reachable at $OLLAMA_URL" >&2
  exit 1
fi

models=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')

if [[ -z "$models" ]]; then
  echo "No models found." >&2
  exit 0
fi

while IFS= read -r model; do
  echo "════════════════════════════════════════════════════════"
  echo "  MODEL: $model"
  echo "════════════════════════════════════════════════════════"
  ollama show "$model"
  echo
done <<< "$models"
