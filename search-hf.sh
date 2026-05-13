#!/usr/bin/env bash
set -euo pipefail
# Search HuggingFace Hub for GGUF model files.
#
# Usage:
#   ./search-hf.sh                                    # search for all unconfigured models in models/*.txt
#   ./search-hf.sh "qwen2.5 coder 14b"               # direct search by query
#   ./search-hf.sh "qwen2.5 coder 32b" --author bartowski  # filter to one HF author/org
#   ./search-hf.sh --limit 3                         # fewer results per model
#   ./search-hf.sh --token hf_xxx                    # explicit auth token (or set HF_TOKEN env var)
#
# Auth: a free HuggingFace account token avoids rate limits.
#   Get one at https://huggingface.co/settings/tokens
#   Then: export HF_TOKEN=hf_xxx  (or pass --token hf_xxx)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "Virtual environment not found at $VENV"
    echo "Run ./run.sh once first to create it."
    exit 1
fi

source "$VENV/bin/activate"
python3 "$SCRIPT_DIR/lib/search_hf.py" "$@"
