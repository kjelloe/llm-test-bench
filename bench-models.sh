# Canonical model list for compare.sh, preflight.sh, and install-models.sh.
# Edit this file to change the benchmark model set — all three scripts pick up the change.
# Order: fastest → slowest by observed avg tok/s (confirmed 2026-04-26; devstral TBD).
#   qwen3-coder:30b    ~36 tok/s  (GPU)
#   qwen2.5-coder:14b  ~41 tok/s  (GPU)
#   devstral-small-2   ~? tok/s   (GPU; Mistral agent-coding model; tok/s TBD)
#   gemma4:26b         ~29 tok/s  (GPU, partial offload)
#   qwen3.5:35b        ~16 tok/s  (RAM-partial; thinking model)
#   gpt-oss:120b       ~11 tok/s  (RAM; thinking model)
MODELS=(
  "qwen3-coder:30b"
  "qwen2.5-coder:14b"
  "devstral-small-2"
  "gemma4:26b"
  "qwen3.5:35b"
  "gpt-oss:120b"
)
