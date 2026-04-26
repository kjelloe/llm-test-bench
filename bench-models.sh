# Canonical model list for compare.sh, preflight.sh, and install-models.sh.
# Edit this file to change the benchmark model set — all three scripts pick up the change.
# Order: fastest → slowest by observed avg tok/s (confirmed 2026-04-26).
#   gpt-oss:20b        ~82 tok/s  (GPU; thinking model, needs --num-predict 2400)
#   qwen2.5-coder:14b  ~40 tok/s  (GPU)
#   qwen3-coder:30b    ~36 tok/s  (GPU)
#   gemma4:26b         ~28 tok/s  (GPU, partial offload)
#   qwen3.5:35b        ~16 tok/s  (RAM-partial; thinking model)
#   gpt-oss:120b       ~11 tok/s  (RAM; thinking model)
MODELS=(
  "gpt-oss:20b"
  "qwen2.5-coder:14b"
  "qwen3-coder:30b"
  "gemma4:26b"
  "qwen3.5:35b"
  "gpt-oss:120b"
)
