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
IS_WSL=false
case "$(uname -s)" in
  Darwin) PLATFORM=macos ;;
  Linux)
    PLATFORM=linux
    grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=true
    ;;
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
[[ "$IS_WSL" == "true" ]] && echo "  WSL2 detected"
[[ -n "$PKG_MGR" ]] && echo "  Package manager: $PKG_MGR"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
VENV="$SCRIPT_DIR/.venv"

# ── 1. Python 3 ───────────────────────────────────────────────────────────────
section "Python 3"
if command -v python3 &>/dev/null; then
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
else
  fail "python3 not found"
  if ask "Install Python 3?"; then
    case "$PLATFORM-$PKG_MGR" in
      linux-apt)    run_cmd "python3" sudo apt-get install -y python3 python3-pip python3-venv ;;
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

# ── 2. Python venv + dependencies ─────────────────────────────────────────────
section "Python venv + dependencies (.venv)"

# On Debian/Ubuntu, venv + ensurepip live in a separate package
if [[ "$PLATFORM-$PKG_MGR" == "linux-apt" ]] && \
   ! python3 -c "import ensurepip" &>/dev/null 2>&1; then
  warn "python3-venv / ensurepip not available"
  if ask "Install python3-venv?"; then
    run_cmd "python3-venv" sudo apt-get install -y python3-venv
  fi
fi

if [[ -d "$VENV" ]]; then
  ok ".venv exists"
else
  fail ".venv not found — required by run.sh and bench.py"
  if ask "Create Python virtual environment at .venv?"; then
    run_cmd "python3 -m venv .venv" python3 -m venv "$VENV"
  fi
fi

# Ensure pip is present in the venv — may be absent on Debian/Ubuntu without python3-pip
if [[ -d "$VENV" ]] && [[ ! -x "$VENV/bin/pip" ]]; then
  info "pip not found in .venv — bootstrapping via ensurepip…"
  if "$VENV/bin/python" -m ensurepip --upgrade &>/dev/null 2>&1; then
    ok "pip bootstrapped"
  else
    warn "ensurepip failed — install python3-pip and recreate the venv:"
    info "  sudo apt-get install -y python3-pip && rm -rf .venv && python3 -m venv .venv"
  fi
fi

if [[ -d "$VENV" ]]; then
  if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
    if [[ ! -x "$VENV/bin/pip" ]]; then
      warn "pip still not available in .venv — skipping requirements install"
      info "Fix: sudo apt-get install -y python3-pip && rm -rf .venv && python3 -m venv .venv"
    elif ask "Install/update Python dependencies from requirements.txt into .venv?"; then
      run_cmd "pip install -r requirements.txt" \
        "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
      if "$VENV/bin/python" -m pytest --version &>/dev/null 2>&1; then
        ok "pytest $("$VENV/bin/python" -m pytest --version 2>&1 | awk '{print $NF}')  (in .venv)"
      fi
    fi
  else
    warn "requirements.txt not found — skipping pip install"
  fi
  info "To run tests: source .venv/bin/activate && python3 -m pytest tests/"
  info "Or directly:  .venv/bin/python -m pytest tests/"
else
  warn "Skipping dependency install — .venv not available"
  info "Create it manually: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
fi

# ── 3. Node.js 20+ and npm ────────────────────────────────────────────────────
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
        sudo bash -c \
          "wget -qO- https://packages.microsoft.com/config/ubuntu/\$(lsb_release -rs)/packages-microsoft-prod.deb -O /tmp/mspkg.deb && dpkg -i /tmp/mspkg.deb" \
          &>/dev/null || true
        sudo apt-get update -qq 2>/dev/null || true
        _dotnet_installed=false
        for _chan in dotnet-sdk-8.0 dotnet-sdk-9.0; do
          if sudo apt-get install -y "$_chan" &>/dev/null 2>&1; then
            ok "$_chan"
            _dotnet_installed=true
            break
          fi
        done
        if [[ "$_dotnet_installed" == "false" ]]; then
          warn "dotnet-sdk not available via apt (Ubuntu 26.04+ ships without it)"
          if ask "Install .NET 9 via the official dotnet-install.sh script?"; then
            if run_cmd "dotnet-install.sh" bash -c \
                "curl -fsSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 9.0 --install-dir \$HOME/.dotnet"; then
              export PATH="$PATH:$HOME/.dotnet"
              grep -qxF 'export PATH=$PATH:$HOME/.dotnet' "$HOME/.bashrc" 2>/dev/null || \
                echo 'export PATH=$PATH:$HOME/.dotnet' >> "$HOME/.bashrc"
              ok ".NET installed to \$HOME/.dotnet — PATH updated in ~/.bashrc"
            fi
          else
            info "Manual install: curl -fsSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 9.0"
            info "Then add to ~/.bashrc: export PATH=\$PATH:\$HOME/.dotnet"
          fi
        fi
        unset _dotnet_installed _chan ;;
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

# ── 5. Java 17+ ───────────────────────────────────────────────────────────────
section "Java 17+ (required for java_* tasks)"
JAVA_OK=false
if command -v java &>/dev/null; then
  JAVA_VER_STR=$(java -version 2>&1 | head -1)
  JAVA_MAJOR=$(java -version 2>&1 | head -1 | sed 's/.*version "\([0-9]*\).*/\1/')
  if [[ "$JAVA_MAJOR" -ge 17 ]]; then
    ok "java  $JAVA_VER_STR"
    if command -v javac &>/dev/null; then
      ok "javac  $(javac -version 2>&1)"
      JAVA_OK=true
    else
      warn "javac not found — install the JDK (not just JRE)"
    fi
  else
    warn "java $JAVA_VER_STR — Java 17+ required"
  fi
fi

if [[ "$JAVA_OK" == "false" ]]; then
  if ask "Install Java 17 JDK?"; then
    case "$PLATFORM-$PKG_MGR" in
      linux-apt)    run_cmd "openjdk-17-jdk" sudo apt-get install -y openjdk-17-jdk ;;
      linux-dnf)    run_cmd "java-17-openjdk-devel" sudo dnf install -y java-17-openjdk-devel ;;
      linux-pacman) run_cmd "jdk-openjdk" sudo pacman -S --noconfirm jdk-openjdk ;;
      macos-*)
        if command -v brew &>/dev/null; then
          run_cmd "openjdk@17" brew install openjdk@17
          info "After install, link it:"
          info "  sudo ln -sfn \$(brew --prefix)/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk"
        else
          fail "Homebrew not found — install from https://brew.sh then retry"
        fi ;;
      *)
        fail "Cannot auto-install Java on this platform."
        info "Download from: https://adoptium.net" ;;
    esac
  fi
fi

# ── 6. Ollama ─────────────────────────────────────────────────────────────────
section "Ollama"
if [[ "$IS_WSL" == "true" ]]; then
  info "WSL2 detected — if Ollama is running on the Windows host, set OLLAMA_URL:"
  info "  export OLLAMA_URL=http://\$(ip route show default | awk '/default/{print \$3}'):11434"
  info "  (current OLLAMA_URL=$OLLAMA_URL)"
fi
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
          if [[ "$PKG_MGR" == "apt" ]] && ! command -v zstd &>/dev/null; then
            info "Installing zstd (required by Ollama installer)…"
            sudo apt-get install -y zstd &>/dev/null || warn "zstd install failed — Ollama installer may fail"
          fi
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

# ── 7. Ollama models ──────────────────────────────────────────────────────────
section "Ollama models (for compare.sh)"
MODELS_FILE="$SCRIPT_DIR/models/default.txt"
REQUIRED_MODELS=()
while IFS= read -r _line || [[ -n "$_line" ]]; do
  _line="${_line%%#*}"                     # strip inline comment
  _line="${_line#"${_line%%[! ]*}"}"       # strip leading whitespace
  [[ -z "$_line" ]] && continue
  _model="${_line%% *}"                    # first field only (ollama name)
  REQUIRED_MODELS+=("$_model")
done < "$MODELS_FILE"
unset _line _model

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

# ── 8. llama-server (optional — required only for --backend llama-server) ─────
section "llama-server (optional)"
_ls_bin="${LLAMA_SERVER_BIN:-$(command -v llama-server 2>/dev/null || true)}"
if [[ -n "$_ls_bin" ]]; then
  ok "llama-server found: $_ls_bin"
  if [[ -n "${LLAMA_MODELS_DIR:-}" ]]; then
    ok "LLAMA_MODELS_DIR=$LLAMA_MODELS_DIR"
  else
    warn "LLAMA_MODELS_DIR not set — add to your ~/.bashrc or ~/.zshrc:"
    info "  export LLAMA_MODELS_DIR=/path/to/gguf/models"
  fi
else
  warn "llama-server not on PATH — needed only for --backend llama-server"
  info "Pre-built binaries: https://github.com/ggerganov/llama.cpp/releases"
  info "After downloading, add to ~/.bashrc or ~/.zshrc:"
  info "  export LLAMA_SERVER_BIN=/path/to/llama-server"
  info "  export LLAMA_MODELS_DIR=/path/to/gguf/models"
fi
unset _ls_bin

# ── 9. vLLM (optional — required only for --backend vllm) ────────────────────
section "vLLM backend (optional)"
if [[ -d "$VENV" ]] && "$VENV/bin/python" -c "import vllm" &>/dev/null 2>&1; then
    VLLM_VER=$("$VENV/bin/python" -c "import vllm; print(vllm.__version__)" 2>/dev/null || echo "unknown")
    ok "vllm $VLLM_VER  (in .venv)"
else
    warn "vllm not installed"
    info "Required only for --backend vllm (tensor-parallel inference, dual-GPU 70B models)"
    info "Installation is large: ~4–8 GB including CUDA libraries"
    _py_minor=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
    if [[ "$_py_minor" -ge 13 ]]; then
      warn "Python 3.$_py_minor detected — vLLM currently supports Python 3.9–3.12 only"
      info "vLLM will likely fail to install on Python 3.$_py_minor"
      info "Install Python 3.12 and create the .venv with it:"
      info "  python3.12 -m venv .venv && .venv/bin/pip install vllm"
    fi
    unset _py_minor
    if ask "Install vllm in .venv now?"; then
        if [[ ! -d "$VENV" ]]; then
            warn ".venv not found — attempting to create it now"
            run_cmd "python3 -m venv .venv" python3 -m venv "$VENV"
        fi
        if [[ -d "$VENV" ]]; then
            if [[ ! -x "$VENV/bin/pip" ]]; then
                fail ".venv/bin/pip not found — pip is missing from the venv"
                info "Fix: $VENV/bin/python -m ensurepip --upgrade"
                info "Then re-run install.sh to retry vllm installation"
            else
                # Install separately: vllm[gguf] extra is not present in all releases
                if run_cmd "vllm" "$VENV/bin/pip" install vllm; then
                    run_cmd "gguf (for --load-format gguf)" "$VENV/bin/pip" install "gguf>=0.10.0"
                fi
            fi
        else
            fail "Cannot create .venv — install Python 3 first (section 1)"
        fi
    else
        info "Skip — to install later:"
        info "  .venv/bin/pip install vllm && .venv/bin/pip install 'gguf>=0.10.0'"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
hr
echo -e "  Done. Run ${BOLD}./preflight.sh${NC} to verify everything is in order."
hr
