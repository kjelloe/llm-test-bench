# Canonical model list for compare.sh, preflight.sh, and install-models.sh.
# Edit this file to change the benchmark model set — all three scripts pick up the change.
# Order: fastest → slowest by observed avg tok/s (confirmed 2026-04-25; 35b tok/s TBD).
#   qwen3-coder:30b              ~45 tok/s  (GPU)
#   qwen2.5-coder:14b            ~41 tok/s  (GPU)
#   gemma4:26b                   ~33 tok/s  (GPU)
#   gpt-oss:120b                 ~12 tok/s  (RAM; first task slower due to load)
#   qwen3.5:35b                   ~? tok/s  (RAM-partial; thinking model; replaces 122b)
#   llama3.3:70b-instruct-q4_K_M  ~2 tok/s  (RAM)
MODELS=(
  "qwen3-coder:30b"
  "qwen2.5-coder:14b"
  "gemma4:26b"
  "gpt-oss:120b"
  "qwen3.5:35b"
  "llama3.3:70b-instruct-q4_K_M"
)
