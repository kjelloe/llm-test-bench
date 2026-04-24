#!/usr/bin/env bash
set -euo pipefail

# Run the full benchmark across all candidate models and print a comparison table.
# Extra flags (e.g. --num-ctx 16384 --tasks python_safe_div) are forwarded to bench.py.

./run.sh \
  --models \
    qwen2.5-coder:32b-instruct-q8_0 \
    gemma4:31b \
    llama3.3:70b-instruct-q4_K_M \
    deepseek-r1:32b \
  --out results-compare.json \
  "$@"
