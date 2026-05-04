#!/usr/bin/env bash
# Interactive installer for ollama-code-bench dependencies.
# Checks each requirement and offers to install anything missing.
# Run ./preflight.sh afterwards to verify everything is in order.
set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; CYAN='\033[0;36m'; NC='\033[0m'

ok()      { echo -e "  ${GREEN}✓${NC}  $*"; }
fail()    { echo -e "  ${RED}✗${NC}  $*"; }
warn()    { echo -e "  ${YELLOW}~${NC}  $*"; }
info()    { echo -e "  ${CYAN}→${NC}  $*"; }
section() { echo; echo -e "${BOLD}── $* ──${NC}"; }
hr()      { echo -e "${BOLD}════════════════════════════════════════${NC}"; }

# ── Platform detection ────────────────────────────────────────────────────────
case "$(uname -s)" in
  Darwin) PLATFORM=macos ;;
  Linux)  PLATFORM=linux ;;
  *)      PLATFORM=unknown ;;
esac

# Detect package manager on Linux
PKG_MGR=""
if [[ "$PLATFORM" == "linux" ]]; then
  if command -v apt-get &>/dev/null; then PKG_MGR=apt
  elif command -v dnf &>/dev/null;     then PKG_MGR=dnf
  elif command -v pacman &>/dev/null;  then PKG_MGR=pacman
  fi
fi

# ask <prompt>  →  returns 0 for yes, 1 for no
ask() {
  local ans
  printf "  %b→%b  %s [Y/n] " "${CYAN}" "${NC}" "$1"
  read -r ans
  [[ -z "$ans" || "$ans" =~ ^[Yy] ]]
}

# run_cmd <description> <command...>  →  runs command, prints outcome
run_cmd() {
  local desc="$1"; shift
  info "Running: $*"
  if "$@"; then
    ok "$desc"
    return 0
  else
    fail "$desc failed — you may need to run this manually"
    return 1
  fi
}

# ── Header ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║  ollama-code-bench  installer        ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"
echo "  Platform: $PLATFORM"
[[ -n "$PKG_MGR" ]] && echo "  Package manager: $PKG_MGR"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"

# ── 1. Python 3 ───────────────────────────────────────────────────────────────
section "Python 3"
if command -v python3 &>/dev/null; then
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
else
  fail "python3 not found"
  if ask "Install Python 3?"; then
    case "$PLATFORM-$PKG_MGR" in
      linux-apt)    run_cmd "python3" sudo apt-get install -y python3 python3-pip ;;
      linux-dnf)    run_cmd "python3" sudo dnf install -y python3 python3-pip ;;
      linux-pacman) run_cmd "python3" sudo pacman -S --noconfirm python python-pip ;;
      macos-*)
        if command -v brew &>/dev/null; then
          run_cmd "python3" brew install python
        else
          fail "Homebrew not found — install from https://brew.sh then retry"
        fi ;;
      *) fail "Unknown platform — install Python 3 from https://python.org" ;;
    esac
  fi
fi

# ── 2. pip + pytest ───────────────────────────────────────────────────────────
section "pytest (Python test runner)"
if python3 -m pytest --version &>/dev/null 2>&1; then
  ok "pytest $(python3 -m pytest --version 2>&1 | awk '{print $NF}')"
else
  fail "pytest not installed"

  # Ensure pip is available before trying to use it
  if ! python3 -m pip --version &>/dev/null 2>&1; then
    warn "pip not found — attempting to install it first"
    PIP_INSTALLED=false
    case "$PLATFORM-$PKG_MGR" in
      linux-apt)    run_cmd "python3-pip" sudo apt-get install -y python3-pip && PIP_INSTALLED=true ;;
      linux-dnf)    run_cmd "python3-pip" sudo dnf install -y python3-pip && PIP_INSTALLED=true ;;
      linux-pacman) run_cmd "python-pip"  sudo pacman -S --noconfirm python-pip && PIP_INSTALLED=true ;;
      *)
        info "Trying ensurepip as fallback…"
        if python3 -m ensurepip --upgrade &>/dev/null 2>&1; then
          ok "pip bootstrapped via ensurepip"
          PIP_INSTALLED=true
        else
          fail "Could not install pip automatically — install it manually and re-run"
        fi ;;
    esac
    # ensurepip fallback for apt/dnf/pacman if the package install failed
    if [[ "$PIP_INSTALLED" == "false" ]] && python3 -m ensurepip --upgrade &>/dev/null 2>&1; then
      ok "pip bootstrapped via ensurepip"
      PIP_INSTALLED=true
    fi
  fi

  if python3 -m pip --version &>/dev/null 2>&1; then
    if ask "Install pytest via pip?"; then
      run_cmd "pytest" python3 -m pip install --user pytest
    fi
  else
    fail "pip still unavailable — cannot install pytest automatically"
    info "Install pip manually, then run: python3 -m pip install --user pytest"
  fi
fi

# ── 3. Node.js + npm ──────────────────────────────────────────────────────────
section "Node.js 20+ and npm"
NODE_OK=false
if command -v node &>/dev/null; then
  NODE_VER=$(node --version 2>&1)
  NODE_MAJOR=$(echo "$NODE_VER" | sed 's/v\([0-9]*\).*/\1/')
  if [[ "$NODE_MAJOR" -ge 20 ]]; then
    ok "node $NODE_VER"
    NODE_OK=true
  else
    warn "node $NODE_VER found — Node 20+ required for the node:test runner"
  fi
fi

if [[ "$NODE_OK" == "false" ]]; then
  if ask "Install Node.js 20 LTS?"; then
    case "$PLATFORM-$PKG_MGR" in
      linux-apt)
        info "Adding NodeSource LTS repository…"
        if run_cmd "NodeSource repo" sudo bash -c \
            "curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -"; then
          run_cmd "nodejs" sudo apt-get install -y nodejs
        fi ;;
      linux-dnf)
        run_cmd "nodejs" sudo dnf install -y nodejs npm ;;
      linux-pacman)
        run_cmd "nodejs" sudo pacman -S --noconfirm nodejs npm ;;
      macos-*)
        if command -v brew &>/dev/null; then
          run_cmd "node" brew install node@20
        else
          fail "Homebrew not found — install from https://brew.sh then retry"
        fi ;;
      *)
        fail "Cannot auto-install on this platform."
        info "Install nvm: https://github.com/nvm-sh/nvm"
        info "Then: nvm install --lts && nvm use --lts" ;;
    esac
  fi
fi

if command -v npm &>/dev/null; then
  ok "npm $(npm --version 2>&1)"
else
  warn "npm not found — usually bundled with Node.js; re-check after installing Node"
fi

# ── 4. .NET SDK 8+ ────────────────────────────────────────────────────────────
section ".NET SDK 8+"
DOTNET_OK=false
if command -v dotnet &>/dev/null; then
  DOTNET_VER=$(dotnet --version 2>&1)
  DOTNET_MAJOR=$(echo "$DOTNET_VER" | cut -d. -f1)
  if [[ "$DOTNET_MAJOR" -ge 8 ]]; then
    ok "dotnet $DOTNET_VER"
    DOTNET_OK=true
  else
    warn "dotnet $DOTNET_VER found — .NET 8+ required by the dotnet_sas task"
  fi
fi

if [[ "$DOTNET_OK" == "false" ]]; then
  if ask "Install .NET SDK 8?"; then
    case "$PLATFORM-$PKG_MGR" in
      linux-apt)
        info "Adding Microsoft package feed…"
        # Works on Ubuntu 20.04+ / Debian 10+
        if run_cmd "Microsoft feed" sudo bash -c \
            "wget -qO- https://packages.microsoft.com/config/ubuntu/\$(lsb_release -rs)/packages-microsoft-prod.deb -O /tmp/mspkg.deb && dpkg -i /tmp/mspkg.deb"; then
          sudo apt-get update -qq
          run_cmd "dotnet-sdk-8.0" sudo apt-get install -y dotnet-sdk-8.0
        fi ;;
      linux-dnf)
        run_cmd "dotnet" sudo dnf install -y dotnet-sdk-8.0 ;;
      macos-*)
        if command -v brew &>/dev/null; then
          run_cmd "dotnet" brew install --cask dotnet-sdk
        else
          fail "Homebrew not found — install from https://brew.sh then retry"
        fi ;;
      *)
        fail "Cannot auto-install .NET on this platform."
        info "Download from: https://dotnet.microsoft.com/download/dotnet/8.0" ;;
    esac
  fi
fi

# ── 5. Ollama ─────────────────────────────────────────────────────────────────
section "Ollama"
OLLAMA_UP=false
if curl -sf --max-time 3 "$OLLAMA_URL" &>/dev/null; then
  ok "Ollama running at $OLLAMA_URL"
  OLLAMA_UP=true
else
  # Is the binary present but not running?
  if command -v ollama &>/dev/null; then
    warn "ollama binary found but server not running at $OLLAMA_URL"
    if ask "Start Ollama server in the background?"; then
      ollama serve &>/dev/null &
      disown
      info "Waiting for Ollama to start…"
      for _ in 1 2 3 4 5; do
        sleep 2
        if curl -sf --max-time 2 "$OLLAMA_URL" &>/dev/null; then
          ok "Ollama started"
          OLLAMA_UP=true
          break
        fi
      done
      [[ "$OLLAMA_UP" == "false" ]] && warn "Ollama did not respond within 10s — check 'ollama serve' manually"
    fi
  else
    fail "Ollama not installed"
    if ask "Install Ollama?"; then
      case "$PLATFORM" in
        linux)
          info "Running official Ollama install script…"
          run_cmd "ollama" bash -c "curl -fsSL https://ollama.ai/install.sh | sh" ;;
        macos)
          if command -v brew &>/dev/null; then
            run_cmd "ollama" brew install ollama
          else
            fail "Homebrew not found."
            info "Download Ollama for macOS from: https://ollama.ai/download"
          fi ;;
        *)
          fail "Cannot auto-install on this platform."
          info "Download from: https://ollama.ai/download" ;;
      esac
      if command -v ollama &>/dev/null; then
        if ask "Start Ollama server now?"; then
          ollama serve &>/dev/null &
          disown
          sleep 3
          curl -sf --max-time 3 "$OLLAMA_URL" &>/dev/null && { ok "Ollama running"; OLLAMA_UP=true; } || \
            warn "Could not confirm Ollama is running — run 'ollama serve' manually"
        fi
      fi
    fi
  fi
fi

# ── 6. Ollama models ──────────────────────────────────────────────────────────
section "Ollama models (for compare.sh)"
MODELS_FILE="$SCRIPT_DIR/models/default.txt"
REQUIRED_MODELS=()
while IFS= read -r _line || [[ -n "$_line" ]]; do
  _line="${_line%%#*}"
  _line="${_line//[[:space:]]/}"
  [[ -n "$_line" ]] && REQUIRED_MODELS+=("$_line")
done < "$MODELS_FILE"
unset _line

# Approximate sizes for user-facing warnings
declare -A MODEL_SIZES=(
  ["gpt-oss:20b"]="13 GB"
  ["qwen2.5-coder:14b"]="9 GB"
  ["qwen3-coder:30b"]="18 GB"
  ["gemma4:26b"]="17 GB"
  ["qwen3.5:35b"]="23 GB"
  ["gpt-oss:120b"]="65 GB"
)

if [[ "$OLLAMA_UP" == "true" ]]; then
  LOADED=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
  for model in "${REQUIRED_MODELS[@]}"; do
    if echo "$LOADED" | grep -qxF "$model"; then
      ok "$model"
    else
      SIZE="${MODEL_SIZES[$model]+${MODEL_SIZES[$model]}}"
      SIZE_NOTE=""
      [[ -n "$SIZE" ]] && SIZE_NOTE=" (~$SIZE download)"
      warn "$model not found${SIZE_NOTE}"
      if ask "Pull $model now?"; then
        run_cmd "$model" ollama pull "$model"
      else
        info "Skip — run later: ollama pull $model"
      fi
    fi
  done
else
  warn "Skipping model check — Ollama is not running"
  info "Start Ollama with: ollama serve"
  info "Then pull models:  ollama pull <model>"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
hr
echo -e "  Done. Run ${BOLD}./preflight.sh${NC} to verify everything is in order."
hr
