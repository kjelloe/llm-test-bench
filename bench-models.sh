# Canonical model list for compare.sh, preflight.sh, and install-models.sh.
# Edit this file to change the benchmark model set — all three scripts pick up the change.
# Order: fastest → slowest by observed tok/s (updated after each run).
MODELS=(
  "qwen3-coder:30b"
  "qwen2.5-coder:14b"
  "gemma4:26b"
  "gpt-oss:120b"
  "qwen3.5:122b"
  "llama3.3:70b-instruct-q4_K_M"
)
