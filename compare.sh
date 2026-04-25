#!/usr/bin/env bash
set -euo pipefail

# Run the full benchmark across all candidate models and print a comparison table.
#
# --num-predict 1200  : thinking models (gemma4, deepseek-r1) need extra tokens for
#                       reasoning before they emit the BEGIN_FILE block; 400 is too few.
# --model-timeout 300 : large models (llama3.3:70b at ~1.7 tok/s) need up to 250s to
#                       generate 400 tokens; the old 120s default timed them out.
#
# Extra flags (e.g. --tasks python_safe_div --num-ctx 16384) are forwarded to bench.py.

./run.sh \
  --models \
    qwen2.5-coder:14b \
    qwen3-coder:30b \
    llama3.3:70b-instruct-q4_K_M \
    qwen3.5:122b \
    gpt-oss:120b \
  --num-predict 1200 \
  --model-timeout 300 \
  --out results-compare.json \
  "$@"
