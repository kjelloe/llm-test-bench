#!/usr/bin/env bash
# Downloads any benchmark models not already present in the local Ollama store.
# Model list is read from bench-models.sh — edit that file to change what gets pulled.
set -euo pipefail

# shellcheck source=bench-models.sh
source "$(dirname "$0")/bench-models.sh"

OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

if ! curl -sf --max-time 3 "$OLLAMA_URL" &>/dev/null; then
  echo "ERROR: Ollama not reachable at $OLLAMA_URL — start with: ollama serve" >&2
  exit 1
fi

LOADED=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')

echo "Checking ${#MODELS[@]} benchmark models..."
echo

for model in "${MODELS[@]}"; do
  if echo "$LOADED" | grep -qxF "$model"; then
    echo "  [already installed]  $model"
  else
    echo "  [pulling]            $model"
    ollama pull "$model"
    echo "  [done]               $model"
  fi
done

echo
echo "All benchmark models are installed. Run ./compare.sh to start the benchmark."
