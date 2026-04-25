#!/usr/bin/env bash
set -euo pipefail

# Run the full benchmark across all candidate models and print a comparison table.
#
# --num-predict 1200  : thinking models (gemma4, deepseek-r1) need extra tokens for
#                       reasoning before they emit the BEGIN_FILE block; 400 is too few.
# --model-timeout 900 : 120B models on RAM (qwen3.5:122b, gpt-oss:120b) can run at
#                       1–2 tok/s; at 1200 tokens that's up to 1200s worst-case.
#                       900s covers most runs without waiting indefinitely on hangs.
#
# Extra flags (e.g. --tasks python_safe_div --num-ctx 16384) are forwarded to bench.py.

# shellcheck source=bench-models.sh
source "$(dirname "$0")/bench-models.sh"

./run.sh \
  --models "${MODELS[@]}" \
  --num-predict 1200 \
  --model-timeout 900 \
  --out results-compare.json \
  "$@"
