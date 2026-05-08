#!/usr/bin/env bash
# configure.sh — Show current environment configuration for ollama-code-bench.
# Read-only: prints current values and the export commands needed to set them.
set -uo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

set_()  { echo -e "  ${GREEN}✓${NC}  ${BOLD}$1${NC}=${CYAN}$2${NC}  ${DIM}$3${NC}"; }
unset_(){ echo -e "  ${YELLOW}~${NC}  ${BOLD}$1${NC}  ${DIM}(unset — $2)${NC}"; }
hint()  { echo -e "       ${DIM}export $1${NC}"; }
section(){ echo; echo -e "${BOLD}── $* ──${NC}"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║  ollama-code-bench  configuration   ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Ollama ────────────────────────────────────────────────────────────────────
section "Ollama"

_v="${OLLAMA_URL:-}"
if [[ -n "$_v" ]]; then
    set_   "OLLAMA_URL" "$_v" "Ollama server address"
else
    unset_ "OLLAMA_URL" "defaults to http://127.0.0.1:11434"
    hint   "OLLAMA_URL=http://127.0.0.1:11434"
fi

# ── llama-server ──────────────────────────────────────────────────────────────
section "llama-server backend"

_v="${LLAMA_SERVER_BIN:-}"
_auto=$(command -v llama-server 2>/dev/null || true)
if [[ -n "$_v" ]]; then
    if [[ -x "$_v" ]]; then
        set_   "LLAMA_SERVER_BIN" "$_v" "llama-server binary (explicit)"
    else
        echo -e "  ${RED}✗${NC}  ${BOLD}LLAMA_SERVER_BIN${NC}=${CYAN}$_v${NC}  ${RED}(file not found or not executable)${NC}"
    fi
elif [[ -n "$_auto" ]]; then
    unset_ "LLAMA_SERVER_BIN" "auto-detected on PATH: $_auto"
    hint   "LLAMA_SERVER_BIN=$_auto"
else
    unset_ "LLAMA_SERVER_BIN" "llama-server not found on PATH"
    hint   "LLAMA_SERVER_BIN=/path/to/llama.cpp/build/bin/llama-server"
    echo -e "       ${DIM}Build it: ./llamacpp/build-llama.sh${NC}"
fi

_v="${LLAMA_MODELS_DIR:-}"
if [[ -n "$_v" ]]; then
    if [[ -d "$_v" ]]; then
        _count=$(find "$_v" -maxdepth 1 -name '*.gguf' 2>/dev/null | wc -l)
        set_   "LLAMA_MODELS_DIR" "$_v" "${_count} GGUF file(s) at top level"
    else
        echo -e "  ${RED}✗${NC}  ${BOLD}LLAMA_MODELS_DIR${NC}=${CYAN}$_v${NC}  ${RED}(directory not found)${NC}"
    fi
else
    unset_ "LLAMA_MODELS_DIR" "required for --backend llama-server and fetch-hf"
    hint   "LLAMA_MODELS_DIR=/path/to/gguf/models"
fi

_v="${BENCH_BACKEND:-}"
if [[ -n "$_v" ]]; then
    set_   "BENCH_BACKEND" "$_v" "default inference backend"
else
    unset_ "BENCH_BACKEND" "defaults to ollama"
    hint   "BENCH_BACKEND=llama-server  # to default to llama-server"
fi

# ── HuggingFace ───────────────────────────────────────────────────────────────
section "HuggingFace  (fetch-hf / search-hf)"

_v="${HF_TOKEN:-}"
if [[ -n "$_v" ]]; then
    # Mask the token — show first 6 chars only
    _masked="${_v:0:6}$(printf '*%.0s' {1..20})"
    set_   "HF_TOKEN" "$_masked" "auth token (masked)"
else
    # Check for cached token from huggingface-cli login
    _cache_token=""
    for _p in "$HOME/.cache/huggingface/token" "$HOME/.huggingface/token"; do
        if [[ -f "$_p" ]]; then
            _cache_token="$_p"
            break
        fi
    done
    if [[ -n "$_cache_token" ]]; then
        unset_ "HF_TOKEN" "unset, but cached token found at $_cache_token (huggingface-cli login)"
        hint   "HF_TOKEN=hf_xxxx  # or rely on the cached token"
    else
        unset_ "HF_TOKEN" "needed for gated models or higher rate limits"
        hint   "HF_TOKEN=hf_xxxx"
        echo -e "       ${DIM}Get a token: https://huggingface.co/settings/tokens${NC}"
        echo -e "       ${DIM}Or run:      huggingface-cli login${NC}"
    fi
fi

# ── llama.cpp build ───────────────────────────────────────────────────────────
section "llama.cpp build  (build-llama.sh)"

_v="${LLAMA_SRC_DIR:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_default_src="$SCRIPT_DIR/llama.cpp"
if [[ -n "$_v" ]]; then
    if [[ -d "$_v" ]]; then
        _commit=$(git -C "$_v" rev-parse --short HEAD 2>/dev/null || echo "unknown")
        set_   "LLAMA_SRC_DIR" "$_v" "source repo  (HEAD: $_commit)"
    else
        echo -e "  ${RED}✗${NC}  ${BOLD}LLAMA_SRC_DIR${NC}=${CYAN}$_v${NC}  ${RED}(directory not found)${NC}"
    fi
elif [[ -d "$_default_src" ]]; then
    _commit=$(git -C "$_default_src" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    unset_ "LLAMA_SRC_DIR" "defaults to ./llama.cpp  (HEAD: $_commit)"
    hint   "LLAMA_SRC_DIR=/custom/path/to/llama.cpp"
else
    unset_ "LLAMA_SRC_DIR" "defaults to ./llama.cpp  (not cloned yet)"
    hint   "LLAMA_SRC_DIR=/path/to/llama.cpp"
    echo -e "       ${DIM}Clone: git clone https://github.com/ggerganov/llama.cpp${NC}"
fi

# ── Persist hint ──────────────────────────────────────────────────────────────
echo
echo -e "${DIM}── To persist across sessions, add export lines to ~/.bashrc or ~/.profile ──${NC}"
echo

