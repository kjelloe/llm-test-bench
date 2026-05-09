#!/usr/bin/env bash
# configure.sh — Show current env config and optionally walk through interactive setup.
# Read phase: prints current state.
# Setup phase (optional): prompts for values, prints final export block.
set -uo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

set_()  { echo -e "  ${GREEN}✓${NC}  ${BOLD}$1${NC}=${CYAN}$2${NC}  ${DIM}$3${NC}"; }
unset_(){ echo -e "  ${YELLOW}~${NC}  ${BOLD}$1${NC}  ${DIM}(unset — $2)${NC}"; }
hint()  { echo -e "       ${DIM}export $1${NC}"; }
section(){ echo; echo -e "${BOLD}── $* ──${NC}"; }
err_()  { echo -e "  ${RED}✗${NC}  ${BOLD}$1${NC}=${CYAN}$2${NC}  ${RED}($3)${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Header ────────────────────────────────────────────────────────────────────
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
        set_ "LLAMA_SERVER_BIN" "$_v" "llama-server binary (explicit)"
    else
        err_ "LLAMA_SERVER_BIN" "$_v" "file not found or not executable"
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
        err_ "LLAMA_MODELS_DIR" "$_v" "directory not found"
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
    _masked="${_v:0:6}$(printf '*%.0s' {1..20})"
    set_   "HF_TOKEN" "$_masked" "auth token (masked)"
else
    _cache_token=""
    for _p in "$HOME/.cache/huggingface/token" "$HOME/.huggingface/token"; do
        if [[ -f "$_p" ]]; then _cache_token="$_p"; break; fi
    done
    if [[ -n "$_cache_token" ]]; then
        unset_ "HF_TOKEN" "unset, but cached token found at $_cache_token"
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
_default_src="$SCRIPT_DIR/llama.cpp"
if [[ -n "$_v" ]]; then
    if [[ -d "$_v" ]]; then
        _commit=$(git -C "$_v" rev-parse --short HEAD 2>/dev/null || echo "unknown")
        set_   "LLAMA_SRC_DIR" "$_v" "source repo  (HEAD: $_commit)"
    else
        err_ "LLAMA_SRC_DIR" "$_v" "directory not found"
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

# ── Interactive setup ─────────────────────────────────────────────────────────
echo
echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"
echo

# Skip wizard if stdin is not a terminal (e.g. piped / CI)
if [[ ! -t 0 ]]; then
    echo -e "${DIM}(stdin is not a terminal — skipping interactive setup)${NC}"
    echo
    exit 0
fi

read -r -p "$(echo -e "${BOLD}Run interactive setup wizard?${NC} [y/N] ")" _run_wizard
if [[ ! "$_run_wizard" =~ ^[Yy]$ ]]; then
    echo
    echo -e "${DIM}Tip: re-run with 'y' to get a ready-to-paste export block.${NC}"
    echo
    exit 0
fi

echo

# Collected values (empty = skip / keep current)
_out_ollama_url=""
_out_llama_bin=""
_out_llama_dir=""
_out_backend=""
_out_hf_token=""

# ── Step 1: Choose backend ────────────────────────────────────────────────────
echo -e "${BOLD}Step 1 — Which backend will you use?${NC}"
echo "  1) ollama         (Ollama must be running locally)"
echo "  2) llama-server   (llama.cpp binary + GGUF files)"
echo "  3) both           (configure all variables)"
echo
while true; do
    read -r -p "Choice [1/2/3]: " _backend_choice
    case "$_backend_choice" in
        1) _configure_ollama=1; _configure_ls=0; break ;;
        2) _configure_ollama=0; _configure_ls=1; break ;;
        3) _configure_ollama=1; _configure_ls=1; break ;;
        *) echo "  Please enter 1, 2, or 3." ;;
    esac
done

# ── Step 2: Ollama URL ────────────────────────────────────────────────────────
if [[ "$_configure_ollama" -eq 1 ]]; then
    echo
    echo -e "${BOLD}Step 2 — Ollama URL${NC}"
    _current_url="${OLLAMA_URL:-http://127.0.0.1:11434}"
    read -r -p "$(echo -e "  OLLAMA_URL [${CYAN}${_current_url}${NC}]: ")" _input
    _out_ollama_url="${_input:-$_current_url}"
    # Normalise: strip trailing slash
    _out_ollama_url="${_out_ollama_url%/}"
    echo -e "  ${GREEN}→${NC} ${_out_ollama_url}"
fi

# ── Step 3: llama-server binary ───────────────────────────────────────────────
if [[ "$_configure_ls" -eq 1 ]]; then
    echo
    echo -e "${BOLD}Step 3 — llama-server binary${NC}"
    _current_bin="${LLAMA_SERVER_BIN:-}"
    if [[ -z "$_current_bin" ]]; then
        _current_bin=$(command -v llama-server 2>/dev/null || true)
    fi
    _prompt_default="${_current_bin:-/path/to/llama.cpp/build/bin/llama-server}"
    read -r -p "$(echo -e "  LLAMA_SERVER_BIN [${CYAN}${_prompt_default}${NC}]: ")" _input
    _out_llama_bin="${_input:-$_current_bin}"
    if [[ -n "$_out_llama_bin" ]]; then
        if [[ -x "$_out_llama_bin" ]]; then
            echo -e "  ${GREEN}✓${NC} Found: $_out_llama_bin"
        else
            echo -e "  ${YELLOW}⚠${NC}  Not found or not executable: $_out_llama_bin  (saved anyway)"
        fi
    fi

    # ── Step 4: GGUF models directory ─────────────────────────────────────────
    echo
    echo -e "${BOLD}Step 4 — GGUF models directory${NC}"
    _current_dir="${LLAMA_MODELS_DIR:-}"
    _prompt_default="${_current_dir:-/path/to/gguf/models}"
    read -r -p "$(echo -e "  LLAMA_MODELS_DIR [${CYAN}${_prompt_default}${NC}]: ")" _input
    _out_llama_dir="${_input:-$_current_dir}"
    if [[ -n "$_out_llama_dir" ]]; then
        if [[ -d "$_out_llama_dir" ]]; then
            _count=$(find "$_out_llama_dir" -maxdepth 1 -name '*.gguf' 2>/dev/null | wc -l)
            echo -e "  ${GREEN}✓${NC} Found: $_out_llama_dir  (${_count} GGUF files at top level)"
        else
            echo -e "  ${YELLOW}⚠${NC}  Directory not found: $_out_llama_dir  (saved anyway)"
        fi
    fi
fi

# ── Step 5: Default backend ───────────────────────────────────────────────────
echo
echo -e "${BOLD}Step 5 — Default backend (BENCH_BACKEND)${NC}"
echo "  This sets which backend compare.sh and run.sh use without --backend."
if [[ "$_configure_ollama" -eq 1 && "$_configure_ls" -eq 0 ]]; then
    _suggested_backend="ollama"
elif [[ "$_configure_ls" -eq 1 && "$_configure_ollama" -eq 0 ]]; then
    _suggested_backend="llama-server"
else
    _suggested_backend="${BENCH_BACKEND:-ollama}"
fi
echo
echo "  1) ollama"
echo "  2) llama-server"
read -r -p "$(echo -e "  Default backend [${CYAN}${_suggested_backend}${NC}]: ")" _input
if [[ "$_input" == "1" ]]; then
    _out_backend="ollama"
elif [[ "$_input" == "2" ]]; then
    _out_backend="llama-server"
elif [[ -z "$_input" ]]; then
    _out_backend="$_suggested_backend"
else
    _out_backend="$_input"
fi
echo -e "  ${GREEN}→${NC} ${_out_backend}"

# ── Step 6: HuggingFace token ─────────────────────────────────────────────────
echo
echo -e "${BOLD}Step 6 — HuggingFace token  ${DIM}(optional — for gated models / higher rate limits)${NC}"
echo -e "  ${DIM}Sign up / log in : https://huggingface.co/join${NC}"
echo -e "  ${DIM}Create a token   : https://huggingface.co/settings/tokens${NC}"
echo -e "  ${DIM}Or run           : huggingface-cli login${NC}"
_cache_token_path=""
for _p in "$HOME/.cache/huggingface/token" "$HOME/.huggingface/token"; do
    if [[ -f "$_p" ]]; then _cache_token_path="$_p"; break; fi
done
if [[ -n "$_cache_token_path" ]]; then
    echo -e "  ${DIM}Cached token found at ${_cache_token_path} — HF_TOKEN env var not required${NC}"
fi
echo
_current_hf="${HF_TOKEN:-}"
if [[ -n "$_current_hf" ]]; then
    _masked="${_current_hf:0:6}$(printf '*%.0s' {1..20})"
    read -r -p "$(echo -e "  HF_TOKEN [${CYAN}${_masked}${NC}] (Enter to keep, type new token or 'skip'): ")" _input
else
    read -r -p "  HF_TOKEN (Enter to skip, or paste token): " _input
fi
if [[ "$_input" == "skip" || ( -z "$_input" && -z "$_current_hf" ) ]]; then
    _out_hf_token=""
    echo -e "  ${DIM}Skipped${NC}"
elif [[ -z "$_input" && -n "$_current_hf" ]]; then
    _out_hf_token="$_current_hf"
    echo -e "  ${GREEN}→${NC} Keeping existing token"
else
    _out_hf_token="$_input"
    echo -e "  ${GREEN}→${NC} Token set"
fi

# ── Step 7: Hardware-aware model optimization (llama-server only) ────────────
if [[ "$_configure_ls" -eq 1 ]]; then
    echo
    echo -e "${BOLD}Step 7 — Hardware-aware model parameter optimization${NC}"
    echo -e "  ${DIM}Suggests ngl, flash_attn, n_cpu_moe, split_mode, etc. based on your GPU and RAM.${NC}"
    echo

    if ! command -v nvidia-smi &>/dev/null; then
        echo -e "  ${YELLOW}~${NC}  nvidia-smi not found — skipping optimization step"
    else
        read -r -p "$(echo -e "  Run optimizer? [Y/n]: ")" _run_opt
        if [[ -z "$_run_opt" || "$_run_opt" =~ ^[Yy]$ ]]; then
            _models_dir="${_out_llama_dir:-${LLAMA_MODELS_DIR:-}}"
            _opt_args=()
            [[ -n "$_models_dir" ]] && _opt_args+=("--models-dir" "$_models_dir")
            echo
            python3 "$SCRIPT_DIR/lib/optimize_models.py" "${_opt_args[@]+"${_opt_args[@]}"}"
        else
            echo -e "  ${DIM}Skipped${NC}"
        fi
    fi
fi

# ── Final export block ────────────────────────────────────────────────────────
echo
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Add these lines to ~/.bashrc (or ~/.profile / ~/.zshrc):${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo

_any=0
_print_export() {
    local name="$1" value="$2"
    echo -e "  ${CYAN}export ${name}=\"${value}\"${NC}"
    _any=1
}

[[ -n "$_out_ollama_url"  ]] && _print_export "OLLAMA_URL"       "$_out_ollama_url"
[[ -n "$_out_backend"     ]] && _print_export "BENCH_BACKEND"    "$_out_backend"
[[ -n "$_out_llama_bin"   ]] && _print_export "LLAMA_SERVER_BIN" "$_out_llama_bin"
[[ -n "$_out_llama_dir"   ]] && _print_export "LLAMA_MODELS_DIR" "$_out_llama_dir"
[[ -n "$_out_hf_token"    ]] && _print_export "HF_TOKEN"         "$_out_hf_token"

if [[ "$_any" -eq 0 ]]; then
    echo -e "  ${DIM}(nothing to export — all values were skipped)${NC}"
fi

echo
echo -e "${DIM}  Then apply immediately with:  source ~/.bashrc${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo

# ── llama-server params reference ────────────────────────────────────────────
if [[ "$_configure_ls" -eq 1 ]]; then
    echo -e "${BOLD}llama-server params reference${NC}  ${DIM}(add to models/*.txt params field)${NC}"
    echo
    echo -e "${GREEN}  Covered — set in models/*.txt or suggested by optimizer:${NC}"
    echo -e "  ${DIM}cache_type_k=q8_0  cache_type_v=q8_0  ngl=999  no_mmap  mlock  n_cpu_moe=35${NC}"
    echo -e "  ${DIM}flash_attn  split_mode=layer  main_gpu=N${NC}"
    echo
    echo -e "${YELLOW}  Supported by model file but not auto-suggested — set manually if needed:${NC}"
    printf "  %-28s %s\n" "batch_size=N"         "Prompt-eval batch size (default 2048; reduce for low VRAM)"
    printf "  %-28s %s\n" "ubatch_size=N"        "Micro-batch size for chunked prompt eval"
    printf "  %-28s %s\n" "threads_batch=N"      "CPU threads for the batch/prompt-eval phase"
    printf "  %-28s %s\n" "rope_freq_base=N"     "RoPE base frequency override (context extension)"
    printf "  %-28s %s\n" "rope_scaling=yarn"    "RoPE scaling method for context extension"
    printf "  %-28s %s\n" "override_kv=..."      "Override model hyperparameters at runtime"
    printf "  %-28s %s\n" "defrag_thold=0.1"     "KV cache defragmentation threshold (0–1)"
    echo
    echo -e "${RED}  Require harness changes — not passable via params field today:${NC}"
    printf "  %-28s %s\n" "--ctx-size N"         "Handled by --num-ctx CLI flag (set per run, not per model)"
    printf "  %-28s %s\n" "--threads N"          "Handled by --num-thread CLI flag"
    echo
fi
