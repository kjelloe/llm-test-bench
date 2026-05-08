#!/usr/bin/env bash
# Pre-flight check: verifies all dependencies before running the benchmark.
set -uo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

PASS=0; FAIL=0; WARN=0

ok()     { echo -e "  ${GREEN}✓${NC}  $*";            PASS=$((PASS + 1)); }
fail()   { echo -e "  ${RED}✗${NC}  $*";              FAIL=$((FAIL + 1)); }
warn()   { echo -e "  ${YELLOW}~${NC}  $*";           WARN=$((WARN + 1)); }
section(){ echo; echo -e "${BOLD}── $* ──${NC}"; }

# Parse all models/*.txt via model_config.py — outputs TSV: name\tgguf_file\thf_repo
# Falls back to empty if Python/lib not available.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_MODELS_TSV=$(python3 - <<PYEOF 2>/dev/null
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from lib.model_config import load_model_file
from pathlib import Path
seen = set()
for f in sorted((Path('$SCRIPT_DIR') / 'models').glob('*.txt')):
    for cfg in load_model_file(f):
        if cfg.ollama_name in seen:
            continue
        seen.add(cfg.ollama_name)
        print('\t'.join([cfg.ollama_name, cfg.gguf_file or '', cfg.hf_repo or '']))
PYEOF
)

OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

echo -e "${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║  ollama-code-bench  preflight check  ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. GPU ────────────────────────────────────────────────────────────────────
section "GPU"
if command -v nvidia-smi &>/dev/null; then
  mapfile -t GPUS < <(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null)
  if [[ ${#GPUS[@]} -gt 0 ]]; then
    for g in "${GPUS[@]}"; do ok "GPU: $g"; done
  else
    warn "nvidia-smi found but no GPUs reported — Ollama may use CPU"
  fi
else
  warn "nvidia-smi not available — Ollama will use CPU (slower)"
fi

# ── 2. Ollama ─────────────────────────────────────────────────────────────────
section "Ollama"
if curl -sf --max-time 3 "$OLLAMA_URL" &>/dev/null; then
  ok "Ollama reachable at $OLLAMA_URL"
  OLLAMA_UP=true
else
  fail "Ollama not reachable at $OLLAMA_URL — start with: ollama serve"
  OLLAMA_UP=false
fi

# ── 3. Models (ollama + GGUF) ─────────────────────────────────────────────────
section "Models  (models/*.txt)"
MODELS_DIR="${LLAMA_MODELS_DIR:-}"

if [[ "$OLLAMA_UP" == "true" ]]; then
  _OLLAMA_LIST=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
else
  _OLLAMA_LIST=""
fi

if [[ -z "$_MODELS_TSV" ]]; then
  warn "Could not parse models/*.txt — is lib/model_config.py present?"
else
  while IFS=$'\t' read -r _name _gguf _hf; do
    [[ -z "$_name" ]] && continue

    # ── ollama status ──
    if [[ "$OLLAMA_UP" == "true" ]]; then
      if echo "$_OLLAMA_LIST" | grep -qxF "$_name"; then
        _ol="${GREEN}ollama ✓${NC}"
        _ol_ok=1
      else
        _ol="${RED}ollama ✗${NC}  (ollama pull $_name)"
        _ol_ok=0
      fi
    else
      _ol="${YELLOW}ollama ?${NC}  (not running)"
      _ol_ok=-1
    fi

    # ── GGUF status ──
    if [[ -z "$_gguf" ]]; then
      _gu="${YELLOW}gguf –${NC}  (not configured)"
      _gu_ok=-1
    elif [[ -z "$MODELS_DIR" ]]; then
      _gu="${YELLOW}gguf ?${NC}  (LLAMA_MODELS_DIR not set)"
      _gu_ok=-1
    elif [[ -f "$MODELS_DIR/$_gguf" ]]; then
      _gu="${GREEN}gguf ✓${NC}  $_gguf"
      _gu_ok=1
    else
      _gu="${RED}gguf ✗${NC}  $_gguf not in \$LLAMA_MODELS_DIR"
      _gu_ok=0
    fi

    # ── pick indicator based on combined status ──
    if   [[ $_ol_ok -eq 1  || $_gu_ok -eq 1  ]]; then
      echo -e "  ${GREEN}✓${NC}  $_name"
      PASS=$((PASS + 1))
    elif [[ $_ol_ok -eq 0  && $_gu_ok -ne 1  ]]; then
      echo -e "  ${RED}✗${NC}  $_name"
      FAIL=$((FAIL + 1))
    else
      echo -e "  ${YELLOW}~${NC}  $_name"
      WARN=$((WARN + 1))
    fi
    echo -e "       $_ol"
    echo -e "       $_gu"

  done <<< "$_MODELS_TSV"
fi
unset _name _gguf _hf _ol _ol_ok _gu _gu_ok _OLLAMA_LIST

# ── 4. Python + pytest ────────────────────────────────────────────────────────
section "Python"
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version 2>&1)
  ok "$PY_VER"
  if python3 -m pytest --version &>/dev/null; then
    ok "pytest  $(python3 -m pytest --version 2>&1 | head -1)"
  else
    fail "pytest not installed — pip install pytest"
  fi
else
  fail "python3 not found"
fi

# ── 5. Node.js + npm ──────────────────────────────────────────────────────────
section "Node.js"
if command -v node &>/dev/null; then
  NODE_VER=$(node --version 2>&1)
  ok "node $NODE_VER"
  # node:test --test <file> requires Node 20+
  NODE_MAJOR=$(echo "$NODE_VER" | sed 's/v\([0-9]*\).*/\1/')
  if [[ "$NODE_MAJOR" -lt 20 ]]; then
    warn "Node $NODE_VER detected — Node 20+ recommended for node:test runner"
  fi
  if command -v npm &>/dev/null; then
    ok "npm $(npm --version 2>&1)"
  else
    fail "npm not found"
  fi
else
  fail "node not found — install from https://nodejs.org"
fi

# ── 6. .NET ───────────────────────────────────────────────────────────────────
section ".NET"
if command -v dotnet &>/dev/null; then
  DOTNET_VER=$(dotnet --version 2>&1)
  ok "dotnet $DOTNET_VER"
  DOTNET_MAJOR=$(echo "$DOTNET_VER" | cut -d. -f1)
  if [[ "$DOTNET_MAJOR" -lt 8 ]]; then
    warn ".NET $DOTNET_VER — .NET 8+ required by the dotnet_sas task"
  fi
else
  fail "dotnet not found — https://dotnet.microsoft.com/download"
fi

# ── 7. llama-server (optional — only needed for --backend llama-server) ───────
section "llama-server (optional)"
_ls_bin="${LLAMA_SERVER_BIN:-$(command -v llama-server 2>/dev/null || true)}"
if [[ -n "$_ls_bin" ]]; then
  ok "llama-server found: $_ls_bin"
  if [[ -n "${LLAMA_MODELS_DIR:-}" ]]; then
    ok "LLAMA_MODELS_DIR=$LLAMA_MODELS_DIR"
  else
    warn "LLAMA_MODELS_DIR not set — required for --backend llama-server"
  fi
else
  warn "llama-server not on PATH — needed only for --backend llama-server"
  warn "  Install: https://github.com/ggerganov/llama.cpp/releases"
  warn "  Or set:  export LLAMA_SERVER_BIN=/path/to/llama-server"
fi
unset _ls_bin

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo -e "${BOLD}════════════════════════════════════════${NC}"
printf "  PASS: %s   FAIL: %s   WARN: %s\n" "$PASS" "$FAIL" "$WARN"
echo -e "${BOLD}════════════════════════════════════════${NC}"

if [[ $FAIL -gt 0 ]]; then
  echo -e "  ${RED}Preflight FAILED — fix the issues above before running.${NC}"
  exit 1
else
  echo -e "  ${GREEN}Preflight OK — ready to run ./compare.sh${NC}"
  exit 0
fi
