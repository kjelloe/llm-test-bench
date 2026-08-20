#!/usr/bin/env bash
# build-llama.sh — Build llama.cpp with CUDA support on Ubuntu.
#
# Expects the repo already cloned at ./llama.cpp (relative to CWD).
# Run from the ollama-code-bench root: ./llamacpp/build-llama.sh
#
# Optional env overrides:
#   LLAMA_SRC_DIR   path to cloned repo  (default: ./llama.cpp)
#   BUILD_DIR       cmake build dir       (default: $LLAMA_SRC_DIR/build)
#   INSTALL_PREFIX  install prefix        (default: /usr/local)
set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "  ${RED}✗${NC}  $*" >&2; }
info() { echo -e "  ${CYAN}→${NC}  $*"; }
section() { echo; echo -e "${BOLD}── $* ──${NC}"; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LLAMA_SRC_DIR="${LLAMA_SRC_DIR:-$REPO_ROOT/llama.cpp}"
BUILD_DIR="${BUILD_DIR:-$LLAMA_SRC_DIR/build}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"

# ── 1. Ubuntu version ─────────────────────────────────────────────────────────
section "System"
if [[ ! -f /etc/os-release ]]; then
    fail "Cannot read /etc/os-release — is this Ubuntu?"
    exit 1
fi
. /etc/os-release
ok "OS: $PRETTY_NAME"
if [[ "${ID:-}" != "ubuntu" ]]; then
    warn "Expected Ubuntu; got '${ID:-unknown}'. Script may still work but is untested."
fi

# ── 2. CUDA version ───────────────────────────────────────────────────────────
section "CUDA"
CUDA_VER=""
CUDA_MAJOR=0
CUDA_MINOR=0
CUDA_HOME=""
NVCC_BIN=""

# Prefer versioned /usr/local/cuda-X.Y dirs over /usr/bin/nvcc.
# The Ubuntu 'nvidia-cuda-toolkit' apt package installs an old nvcc at /usr/bin/nvcc
# (CUDA 12.0) that is incompatible with GCC 13. The proper toolkit lives under
# /usr/local/cuda-X.Y and is symlinked via /usr/local/cuda.
for _cuda_dir in $(ls -d /usr/local/cuda-[0-9]* 2>/dev/null | sort -V -r || true) /usr/local/cuda; do
    if [[ -x "$_cuda_dir/bin/nvcc" ]]; then
        CUDA_HOME="$(realpath "$_cuda_dir")"
        NVCC_BIN="$CUDA_HOME/bin/nvcc"
        break
    fi
done

# Fall back to whatever nvcc is in PATH
if [[ -z "$NVCC_BIN" ]] && command -v nvcc &>/dev/null; then
    NVCC_BIN="$(command -v nvcc)"
fi

if [[ -n "$NVCC_BIN" ]]; then
    CUDA_VER=$("$NVCC_BIN" --version 2>/dev/null | grep -oP 'release \K[0-9]+\.[0-9]+' | head -1 || true)
fi

# Fall back to version file
if [[ -z "$CUDA_VER" && -f /usr/local/cuda/version.json ]]; then
    CUDA_VER=$(python3 -c "import json; d=json.load(open('/usr/local/cuda/version.json')); \
        print(d.get('cuda',d.get('CUDA Version',{}).get('version','')))" 2>/dev/null || true)
fi
if [[ -z "$CUDA_VER" && -f /usr/local/cuda/version.txt ]]; then
    CUDA_VER=$(grep -oP 'CUDA Version \K[0-9]+\.[0-9]+' /usr/local/cuda/version.txt 2>/dev/null || true)
fi
# Fall back to nvidia-smi
if [[ -z "$CUDA_VER" ]] && command -v nvidia-smi &>/dev/null; then
    CUDA_VER=$(nvidia-smi 2>/dev/null | grep -oP 'CUDA Version: \K[0-9]+\.[0-9]+' | head -1 || true)
fi

if [[ -z "$CUDA_VER" ]]; then
    warn "CUDA toolkit (nvcc) not found."

    # On WSL2 the GPU driver is provided by Windows; check it is accessible before
    # offering to install the toolkit, since without it the install would be pointless.
    if command -v nvidia-smi &>/dev/null; then
        if nvidia-smi &>/dev/null; then
            _smi_cuda=$(nvidia-smi 2>/dev/null | grep -oP 'CUDA Version: \K[0-9.]+' || true)
            info "GPU driver OK (nvidia-smi reports CUDA ${_smi_cuda:-unknown})"
        else
            fail "nvidia-smi found but failed — GPU driver may not be set up for WSL2."
            fail "  See: https://docs.nvidia.com/cuda/wsl-user-guide/"
            exit 1
        fi
    else
        warn "nvidia-smi not found — continuing anyway (non-WSL2 install may still work)."
    fi

    echo
    info "Install nvidia-cuda-toolkit from Ubuntu's repo? (~2 GB download)"
    read -r -p "  [y/N] " _do_install_cuda
    if [[ "${_do_install_cuda,,}" != "y" ]]; then
        fail "Cannot build without CUDA toolkit."
        fail "  Manual install: https://developer.nvidia.com/cuda-downloads"
        exit 1
    fi

    info "Installing nvidia-cuda-toolkit..."
    if [[ "$EUID" -ne 0 ]]; then
        sudo apt-get install -y nvidia-cuda-toolkit
    else
        apt-get install -y nvidia-cuda-toolkit
    fi

    # nvidia-cuda-toolkit installs nvcc to /usr/bin/nvcc; re-detect from PATH.
    NVCC_BIN="$(command -v nvcc 2>/dev/null || true)"
    if [[ -n "$NVCC_BIN" ]]; then
        CUDA_VER=$("$NVCC_BIN" --version 2>/dev/null | grep -oP 'release \K[0-9]+\.[0-9]+' | head -1 || true)
    fi
    if [[ -z "$CUDA_VER" ]]; then
        fail "nvidia-cuda-toolkit installed but nvcc still not detected."
        fail "  Try opening a new terminal and re-running."
        exit 1
    fi
    ok "CUDA toolkit installed: $CUDA_VER"
fi

CUDA_MAJOR=$(echo "$CUDA_VER" | cut -d. -f1)
CUDA_MINOR=$(echo "$CUDA_VER" | cut -d. -f2)
ok "CUDA $CUDA_VER  (nvcc: ${NVCC_BIN:-not found})"
[[ -n "$CUDA_HOME" ]] && info "CUDA_HOME: $CUDA_HOME"

# Prepend the proper CUDA bin dir to PATH so cmake and the build also pick it up.
if [[ -n "$CUDA_HOME" ]]; then
    export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

# Detect all GPU compute capabilities. On mixed systems (e.g. RTX 4090 + RTX 5060 Ti)
# cmake would otherwise try to compile for every detected architecture, including
# Blackwell (sm_120+) which requires CUDA 12.8 and hard-fails with older nvcc.
GPU_SMS=()
if command -v nvidia-smi &>/dev/null; then
    while IFS= read -r _cap; do
        [[ -n "$_cap" ]] && GPU_SMS+=("$(echo "$_cap" | tr -d '.')")
    done < <(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null || true)
fi

# Split into GPUs the current CUDA can handle vs. Blackwell (sm_120+) that need 12.8.
SUPPORTED_SMS=()
BLACKWELL_SMS=()
CUDA_HAS_BLACKWELL_SUPPORT=$(( CUDA_MAJOR > 12 || (CUDA_MAJOR == 12 && CUDA_MINOR >= 8) ))
for _sm in "${GPU_SMS[@]}"; do
    if (( _sm >= 120 )) && (( ! CUDA_HAS_BLACKWELL_SUPPORT )); then
        BLACKWELL_SMS+=("$_sm")
    else
        SUPPORTED_SMS+=("$_sm")
    fi
done

if [[ ${#GPU_SMS[@]} -gt 0 ]]; then
    ok "GPUs detected: ${GPU_SMS[*]/#/sm_}"
fi

if [[ ${#BLACKWELL_SMS[@]} -gt 0 ]]; then
    warn "Blackwell GPU(s) (sm_${BLACKWELL_SMS[*]}) excluded — CUDA $CUDA_VER < 12.8."
    warn "  To enable RTX 5000-series GPUs, install CUDA 12.8+:"
    warn "    sudo apt-get install cuda-toolkit-12-8   # if NVIDIA repo is configured"
    warn "    or: https://developer.nvidia.com/cuda-downloads"
fi

if [[ ${#SUPPORTED_SMS[@]} -eq 0 ]]; then
    fail "No GPUs supported by CUDA $CUDA_VER. All detected GPUs require CUDA 12.8+."
    fail "  Install CUDA 12.8: https://developer.nvidia.com/cuda-downloads"
    exit 1
fi

# ── 3. Source repo ────────────────────────────────────────────────────────────
section "Source"
if [[ ! -d "$LLAMA_SRC_DIR" ]]; then
    fail "llama.cpp repo not found at: $LLAMA_SRC_DIR"
    fail "  Clone it first:  git clone https://github.com/ggerganov/llama.cpp $LLAMA_SRC_DIR"
    exit 1
fi
if [[ ! -f "$LLAMA_SRC_DIR/CMakeLists.txt" ]]; then
    fail "No CMakeLists.txt in $LLAMA_SRC_DIR — incomplete clone?"
    exit 1
fi
COMMIT=$(git -C "$LLAMA_SRC_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git -C "$LLAMA_SRC_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
ok "Repo: $LLAMA_SRC_DIR  ($BRANCH @ $COMMIT)"

# ── 4. Dependencies ───────────────────────────────────────────────────────────
section "Dependencies"
PKGS=()
for pkg in cmake build-essential libcurl4-openssl-dev git; do
    if dpkg -s "$pkg" &>/dev/null; then
        ok "$pkg"
    else
        warn "$pkg not installed — will install"
        PKGS+=("$pkg")
    fi
done

if [[ ${#PKGS[@]} -gt 0 ]]; then
    info "Installing: ${PKGS[*]}"
    if [[ "$EUID" -ne 0 ]]; then
        sudo apt-get update -qq
        sudo apt-get install -y "${PKGS[@]}"
    else
        apt-get update -qq
        apt-get install -y "${PKGS[@]}"
    fi
    ok "Dependencies installed"
fi

# ── 5. Previous build directory ───────────────────────────────────────────────
section "Build directory"
if [[ -d "$BUILD_DIR" ]]; then
    _prev_bin="$BUILD_DIR/bin/llama-server"
    if [[ -f "$_prev_bin" ]]; then
        _prev_status="successful build"
        _prev_ver=$("$_prev_bin" --version 2>&1 || true)
        warn "Existing build found: $BUILD_DIR"
        warn "  Binary : $_prev_bin"
        warn "  Version: $_prev_ver"
        read -r -p "  Clean for a fresh rebuild? [y/N] " _clean
    else
        _prev_status="incomplete or failed build"
        warn "Incomplete/failed build directory found: $BUILD_DIR"
        read -r -p "  Clean it before rebuilding? [y/N] " _clean
    fi
    if [[ "${_clean,,}" == "y" ]]; then
        info "Removing $BUILD_DIR ..."
        rm -rf "$BUILD_DIR"
        ok "Cleaned"
    else
        info "Keeping existing directory — cmake will do an incremental build"
    fi
else
    ok "No previous build directory"
fi

# ── 6. CMake build ────────────────────────────────────────────────────────────
section "Build"
JOBS=$(nproc)
# Build for supported GPUs. Omit the -real suffix so cmake also emits PTX alongside
# native code; the driver then JIT-compiles it for any newer GPU at runtime (e.g.
# a Blackwell card alongside the primary sm_89 GPU).
CUDA_ARCH_FLAG=""
if [[ ${#SUPPORTED_SMS[@]} -gt 0 ]]; then
    _arch_list=$(IFS=';'; echo "${SUPPORTED_SMS[*]}")
    CUDA_ARCH_FLAG="-DCMAKE_CUDA_ARCHITECTURES=${_arch_list}"
fi
info "Build dir : $BUILD_DIR"
info "Flags     : -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release${NVCC_BIN:+ -DCMAKE_CUDA_COMPILER=$NVCC_BIN}${CUDA_ARCH_FLAG:+ $CUDA_ARCH_FLAG}"
info "Cores     : $JOBS"
echo

cmake \
    -S "$LLAMA_SRC_DIR" \
    -B "$BUILD_DIR" \
    -DGGML_CUDA=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    ${NVCC_BIN:+-DCMAKE_CUDA_COMPILER="$NVCC_BIN"} \
    ${CUDA_ARCH_FLAG:+$CUDA_ARCH_FLAG}

echo
cmake --build "$BUILD_DIR" --config Release -j"$JOBS"

# ── 7. Verify binary ─────────────────────────────────────────────────────────
section "Verify"
SERVER_BIN="$BUILD_DIR/bin/llama-server"
CLI_BIN="$BUILD_DIR/bin/llama-cli"

if [[ ! -f "$SERVER_BIN" ]]; then
    fail "llama-server not found at $SERVER_BIN — build may have failed"
    exit 1
fi
ok "llama-server: $SERVER_BIN"

# Print version (llama-server --version exits 0 on recent builds)
VER_OUT=$("$SERVER_BIN" --version 2>&1 || true)
info "Version: $VER_OUT"

if [[ -f "$CLI_BIN" ]]; then
    ok "llama-cli:    $CLI_BIN"
fi

# ── 8. Optional install ───────────────────────────────────────────────────────
section "Install"
echo -e "  Install ${BOLD}llama-server${NC} (and llama-cli if built) to ${INSTALL_PREFIX}/bin?"
read -r -p "  [y/N] " _install
if [[ "${_install,,}" == "y" ]]; then
    if [[ "$EUID" -ne 0 ]]; then
        sudo cmake --install "$BUILD_DIR" --component Runtime 2>/dev/null || \
        sudo install -m 755 "$SERVER_BIN" "${INSTALL_PREFIX}/bin/llama-server"
        [[ -f "$CLI_BIN" ]] && sudo install -m 755 "$CLI_BIN" "${INSTALL_PREFIX}/bin/llama-cli"
    else
        cmake --install "$BUILD_DIR" --component Runtime 2>/dev/null || \
        install -m 755 "$SERVER_BIN" "${INSTALL_PREFIX}/bin/llama-server"
        [[ -f "$CLI_BIN" ]] && install -m 755 "$CLI_BIN" "${INSTALL_PREFIX}/bin/llama-cli"
    fi
    ok "Installed to ${INSTALL_PREFIX}/bin/"
    info "Verify: llama-server --version"
    info "Or set: export LLAMA_SERVER_BIN=$SERVER_BIN"
else
    info "Skipped. To use without installing, set:"
    info "  export LLAMA_SERVER_BIN=$SERVER_BIN"
fi

# ── 9. Optional systemd service ───────────────────────────────────────────────
section "systemd service (optional)"
echo "  Install a systemd service for llama-server?"
echo "  It will use MoE-optimised flags:"
echo "    --n-gpu-layers 999 --n-cpu-moe 35 --no-mmap --mlock"
echo "    --cache-type-k turbo4 --cache-type-v turbo3"
echo "  You will be prompted for the model path."
read -r -p "  [y/N] " _svc
if [[ "${_svc,,}" == "y" ]]; then
    # Resolve the binary to use (installed or local build)
    if command -v llama-server &>/dev/null; then
        _svc_bin="$(command -v llama-server)"
    else
        _svc_bin="$SERVER_BIN"
    fi

    read -r -p "  GGUF model path (full path): " _model_path
    if [[ ! -f "$_model_path" ]]; then
        warn "File not found: $_model_path — service will be created but may fail to start"
    fi

    read -r -p "  Port [8080]: " _port
    _port="${_port:-8080}"

    read -r -p "  Context size [8192]: " _ctx
    _ctx="${_ctx:-8192}"

    SERVICE_FILE=/etc/systemd/system/llama-server.service
    cat > /tmp/llama-server.service <<EOF
[Unit]
Description=llama-server (llama.cpp inference server)
After=network.target

[Service]
Type=simple
ExecStart=${_svc_bin} \\
    -m ${_model_path} \\
    --host 127.0.0.1 \\
    --port ${_port} \\
    --ctx-size ${_ctx} \\
    --n-gpu-layers 999 \\
    --n-cpu-moe 35 \\
    --no-mmap \\
    --mlock \\
    --cache-type-k turbo4 \\
    --cache-type-v turbo3
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    if [[ "$EUID" -ne 0 ]]; then
        sudo mv /tmp/llama-server.service "$SERVICE_FILE"
        sudo systemctl daemon-reload
        sudo systemctl enable llama-server
    else
        mv /tmp/llama-server.service "$SERVICE_FILE"
        systemctl daemon-reload
        systemctl enable llama-server
    fi

    ok "Service installed: $SERVICE_FILE"
    info "Start:  sudo systemctl start llama-server"
    info "Status: sudo systemctl status llama-server"
    info "Logs:   journalctl -u llama-server -f"
    info "To change the model, edit $SERVICE_FILE and run: sudo systemctl restart llama-server"
else
    info "Skipped."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
echo -e "${BOLD}${GREEN}════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Build complete${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════${NC}"
echo -e "  Binary : $SERVER_BIN"
echo -e "  Version: $VER_OUT"
echo -e "  To benchmark: export LLAMA_SERVER_BIN=$SERVER_BIN"
echo -e "                export LLAMA_MODELS_DIR=/path/to/models"
echo -e "                ./compare.sh --backend llama-server"
echo
