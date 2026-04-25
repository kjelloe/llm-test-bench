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

# ── models that compare.sh will benchmark ────────────────────────────────────
# shellcheck source=bench-models.sh
source "$(dirname "$0")/bench-models.sh"
REQUIRED_MODELS=("${MODELS[@]}")

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

# ── 3. Required models ────────────────────────────────────────────────────────
section "Ollama models"
if [[ "$OLLAMA_UP" == "true" ]]; then
  LOADED_MODELS=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
  for model in "${REQUIRED_MODELS[@]}"; do
    if echo "$LOADED_MODELS" | grep -qxF "$model"; then
      ok "$model"
    else
      fail "$model  →  ollama pull $model"
    fi
  done
else
  warn "Skipping model check — Ollama not running"
fi

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

# ── 7. Aider (optional) ───────────────────────────────────────────────────────
section "Aider (optional — not used by benchmark)"
if command -v aider &>/dev/null; then
  ok "aider $(aider --version 2>&1 | head -1)"
else
  warn "aider not found — not required"
fi

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
