#!/usr/bin/env bash
# my-build.sh — Install vLLM from this checkout into its own venv, using prebuilt kernels
# (VLLM_USE_PRECOMPILED=1, no CUDA compile), and optionally build vllm-gguf-plugin into the
# same venv. Written for the RTX 5060 Ti (Blackwell, sm_120) box, first under WSL2, since
# 2026-09-22 bare-metal Ubuntu; see llm-test-bench/test-plan-5060ti.md, Part B.
#
# Why not just `pip install vllm`: the SM120 speedups this box needs (13cf9e05c1: W4A4 NVFP4
# kernels preferred on SM120; f6326f53bd: FlashInfer GDN prefill on SM12x) landed on main on
# 2026-09-08, after the 0.29.0 release. The build checks for both and warns if they are missing:
# the 2026-09-06 build lacked them unnoticed until 2026-09-24.
#
# By default the checkout is copied to ~/src/vllm first (under WSL this checkout lived on /mnt/c,
# 9p, where an editable install imports slowly). Only committed changes are copied.
#
# Precompiled wheels appear on wheels.vllm.ai some hours after a commit merges, so a freshly
# merged HEAD often has none yet. --latest-wheel builds the newest commit at or below HEAD that
# is on upstream/main and has a wheel, instead of falling back to a mismatched --nightly.
#
# Keep a working install while trying a new one: build side by side, then point VLLM_BIN at it.
#   BUILD_SRC=~/src/vllm-next VENV_DIR=~/vllm-env-next ./my-build.sh --latest-wheel
#
# Usage: ./my-build.sh [options]
#   --with-plugin     also build vllm-gguf-plugin into the venv (needed for GGUF models only)
#   --force-plugin    build the plugin even if PyTorch's CUDA major != nvcc's (likely to fail)
#   --in-place        install from this checkout directly, skip the ext4 copy
#   --recreate-venv   delete and recreate the venv
#   --nightly         use the newest already-built nightly wheel instead of this exact commit's
#                     (only if this commit's wheel isn't published yet; kernels may not match)
#   --latest-wheel    build the newest upstream/main commit at or below HEAD that has a wheel
#   --commit=SHA      build this commit instead of HEAD (must be on a branch of the checkout)
#   -h, --help        show this help
#
# Env overrides:
#   VLLM_SRC          vLLM checkout to build           (default: this script's directory)
#   BUILD_SRC         ext4 copy that gets installed    (default: ~/src/vllm)
#   VENV_DIR          venv to create/use               (default: ~/vllm-env)
#   PYTHON_VERSION    Python for the venv              (default: 3.12)
#   PLUGIN_SRC        vllm-gguf-plugin checkout        (default: $VLLM_SRC/../vllm-gguf-plugin)
#   PLUGIN_BUILD_SRC  ext4 copy of the plugin          (default: ~/src/vllm-gguf-plugin)
set -euo pipefail

# ── Colour helpers (same as llm-test-bench/llamacpp/build-llama.sh) ───────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "  ${RED}✗${NC}  $*" >&2; }
info() { echo -e "  ${CYAN}→${NC}  $*"; }
section() { echo; echo -e "${BOLD}── $* ──${NC}"; }
die() { fail "$*"; exit 1; }

# ── Options ───────────────────────────────────────────────────────────────────
WITH_PLUGIN=0; FORCE_PLUGIN=0; IN_PLACE=0; RECREATE_VENV=0; NIGHTLY=0; LATEST_WHEEL=0; COMMIT=""
for arg in "$@"; do
    case "$arg" in
        --with-plugin)   WITH_PLUGIN=1 ;;
        --force-plugin)  WITH_PLUGIN=1; FORCE_PLUGIN=1 ;;
        --in-place)      IN_PLACE=1 ;;
        --recreate-venv) RECREATE_VENV=1 ;;
        --nightly)       NIGHTLY=1 ;;
        --latest-wheel)  LATEST_WHEEL=1 ;;
        --commit=*)      COMMIT="${arg#--commit=}" ;;
        -h|--help)       sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *)               die "Unknown option: $arg (see --help)" ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VLLM_SRC="$(realpath "${VLLM_SRC:-$SCRIPT_DIR}")"
BUILD_SRC="${BUILD_SRC:-$HOME/src/vllm}"
VENV_DIR="${VENV_DIR:-$HOME/vllm-env}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
PLUGIN_SRC="${PLUGIN_SRC:-$VLLM_SRC/../vllm-gguf-plugin}"
PLUGIN_BUILD_SRC="${PLUGIN_BUILD_SRC:-$HOME/src/vllm-gguf-plugin}"
VPY="$VENV_DIR/bin/python"
# Commits this box's speedups depend on (see the header). Missing ones are a warning, not an error.
REQUIRED_COMMITS=(13cf9e05c1 f6326f53bd)
(( NIGHTLY && LATEST_WHEEL )) && die "--nightly and --latest-wheel are exclusive"
[[ -n "$COMMIT" ]] && (( LATEST_WHEEL )) && die "--commit and --latest-wheel are exclusive"

fs_type() { findmnt -T "$(realpath "$1")" -n -o FSTYPE 2>/dev/null || echo unknown; }

# Copy a checkout's committed HEAD to an ext4 clone, on a named branch. A named branch
# matters: vLLM's setup.py runs `git merge-base <upstream main> <current branch>`, which
# fails on a detached HEAD and silently falls back to the nightly wheel.
sync_checkout() {
    local src="$1" dst="$2" sha="${3:-}"
    [[ -n "$sha" ]] || sha="$(git -C "$src" rev-parse HEAD)"
    if ! git -C "$src" diff --quiet HEAD -- 2>/dev/null; then
        warn "$src has uncommitted changes to tracked files; they are NOT copied (commit them first)"
    fi
    if [[ ! -d "$dst/.git" ]]; then
        mkdir -p "$(dirname "$dst")"
        info "Cloning $src -> $dst (local copy, no network)"
        git clone --quiet --no-checkout "$src" "$dst"
    else
        if ! git -C "$dst" diff --quiet HEAD -- 2>/dev/null; then
            die "$dst has local changes; move them aside or delete $dst, then rerun"
        fi
        info "Updating $dst from $src"
        git -C "$dst" fetch --quiet origin '+refs/heads/*:refs/remotes/origin/*'
    fi
    git -C "$dst" cat-file -e "$sha" 2>/dev/null \
        || die "Commit $sha is not on any branch of $src (detached HEAD?); check out a branch there"
    git -C "$dst" checkout --quiet -B my-build "$sha"
    ok "$dst at ${sha:0:10} (branch my-build)"
}

# ── 1. System ─────────────────────────────────────────────────────────────────
section "System"
for tool in git uv curl findmnt; do
    command -v "$tool" &>/dev/null || die "'$tool' not found on PATH"
done
ok "git, uv, curl present"
command -v nvidia-smi &>/dev/null || die "nvidia-smi not found (no NVIDIA driver visible)"
while IFS=, read -r name cap mem; do
    ok "GPU: $name (compute capability${cap}, ${mem# })"
done < <(nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader)
[[ -d "$VLLM_SRC/.git" && -f "$VLLM_SRC/setup.py" ]] || die "$VLLM_SRC is not a vLLM checkout"
ok "vLLM source: $VLLM_SRC [$(fs_type "$VLLM_SRC")]"

# ── 2. Source ─────────────────────────────────────────────────────────────────
section "Source"
has_wheel() { [[ "$(curl -s -o /dev/null -w '%{http_code}' "https://wheels.vllm.ai/$1/vllm/")" == 200 ]]; }
if [[ -n "$COMMIT" ]]; then
    SRC_SHA="$(git -C "$VLLM_SRC" rev-parse --verify --quiet "$COMMIT^{commit}")" \
        || die "--commit=$COMMIT: no such commit in $VLLM_SRC"
elif (( LATEST_WHEEL )); then
    git -C "$VLLM_SRC" rev-parse --verify --quiet upstream/main >/dev/null \
        || die "--latest-wheel needs an 'upstream' remote with main fetched (git fetch upstream)"
    SRC_SHA=""
    head_sha="$(git -C "$VLLM_SRC" rev-parse HEAD)"
    base="$(git -C "$VLLM_SRC" merge-base "$head_sha" upstream/main)"
    info "Looking for the newest wheel at or below ${base:0:10} (probing wheels.vllm.ai)"
    for c in $(git -C "$VLLM_SRC" rev-list --first-parent -n 48 "$base"); do
        if has_wheel "$c"; then SRC_SHA="$c"; break; fi
    done
    [[ -n "$SRC_SHA" ]] || die "No wheel among the last 48 upstream commits below ${base:0:10}"
    [[ "$SRC_SHA" == "$head_sha" ]] \
        || warn "HEAD ${head_sha:0:10} has no wheel yet; building ${SRC_SHA:0:10} ($(git -C "$VLLM_SRC" rev-list --count "$SRC_SHA..$head_sha") commits older)"
else
    SRC_SHA="$(git -C "$VLLM_SRC" rev-parse HEAD)"
fi
info "$(git -C "$VLLM_SRC" log -1 --format='%h %cs %s' "$SRC_SHA")"
for c in "${REQUIRED_COMMITS[@]}"; do
    if git -C "$VLLM_SRC" merge-base --is-ancestor "$c" "$SRC_SHA" 2>/dev/null; then
        ok "contains $c ($(git -C "$VLLM_SRC" log -1 --format=%s "$c" | cut -c1-70))"
    else
        warn "does NOT contain $c: this box's SM120 speedups are missing (merge upstream/main)"
    fi
done
if (( IN_PLACE )); then
    [[ "$SRC_SHA" == "$(git -C "$VLLM_SRC" rev-parse HEAD)" ]] \
        || die "--in-place installs the working tree, so it cannot build another commit; drop --in-place"
    INSTALL_SRC="$VLLM_SRC"
    [[ "$(fs_type "$VLLM_SRC")" == "9p" ]] \
        && warn "Installing in place on /mnt/c (9p): imports will be slow. Drop --in-place to copy to ext4."
    [[ -n "$(git -C "$VLLM_SRC" branch --show-current)" ]] \
        || die "Detached HEAD in $VLLM_SRC: setup.py needs a branch to find its wheel. Check out a branch."
else
    sync_checkout "$VLLM_SRC" "$BUILD_SRC" "$SRC_SHA"
    INSTALL_SRC="$BUILD_SRC"
fi

# ── 3. Which prebuilt wheel ───────────────────────────────────────────────────
section "Prebuilt kernels"
if (( NIGHTLY )); then
    export VLLM_PRECOMPILED_WHEEL_COMMIT=nightly
    warn "Using the newest nightly wheel; its compiled kernels may not match this source commit"
elif git -C "$VLLM_SRC" rev-parse --verify --quiet upstream/main >/dev/null \
     && git -C "$VLLM_SRC" merge-base --is-ancestor "$SRC_SHA" upstream/main; then
    export VLLM_PRECOMPILED_WHEEL_COMMIT="$SRC_SHA"
    ok "Commit is on upstream/main: pinning the wheel to ${SRC_SHA:0:10} (no GitHub API lookup)"
else
    info "Commit is not on upstream/main (dev branch?): setup.py will find the merge-base with"
    info "upstream main itself (queries the GitHub API and may git-fetch from github.com)"
fi
export VLLM_USE_PRECOMPILED=1

# ── 4. Venv ───────────────────────────────────────────────────────────────────
section "Venv"
if (( RECREATE_VENV )) && [[ -d "$VENV_DIR" ]]; then
    [[ -f "$VENV_DIR/pyvenv.cfg" ]] || die "$VENV_DIR doesn't look like a venv; refusing to delete it"
    info "Removing $VENV_DIR"
    rm -rf "$VENV_DIR"
fi
if [[ -x "$VPY" ]]; then
    ok "Reusing $VENV_DIR ($("$VPY" --version))"
else
    uv venv --quiet "$VENV_DIR" --python "$PYTHON_VERSION"
    ok "Created $VENV_DIR ($("$VPY" --version))"
fi

# ── 5. Install vLLM ───────────────────────────────────────────────────────────
section "Install vLLM (editable, prebuilt kernels)"
info "uv pip install --editable $INSTALL_SRC --torch-backend=auto"
if ! (cd "$INSTALL_SRC" && uv pip install --python "$VPY" --editable . --torch-backend=auto); then
    fail "vLLM install failed."
    if [[ "${VLLM_PRECOMPILED_WHEEL_COMMIT:-}" != "nightly" ]]; then
        info "If the error says the wheel wasn't found, this commit's wheel may not be built yet"
        info "(usually within ~1 hour of the merge). Wait and retry, or rerun with --nightly."
    fi
    exit 1
fi
ok "vLLM installed"

# ── 6. Verify ─────────────────────────────────────────────────────────────────
section "Verify"
# Run from /tmp: from inside a vLLM source tree, Python imports that tree's vllm/ package
# instead of the installed one, so the check would pass (or fail) for the wrong code.
(cd /tmp && EXPECT_SRC="$(realpath "$INSTALL_SRC")" "$VPY" - <<'EOF'
import os, torch, vllm
import vllm.vllm_flash_attn  # needs the compiled kernels; fails if they're missing or stale
cap = torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None
src = os.path.dirname(os.path.dirname(os.path.realpath(vllm.__file__)))
print(f"  vllm {vllm.__version__} from {src}")
print(f"  torch {torch.__version__} (CUDA {torch.version.cuda})")
print(f"  GPU capability {cap} | sm_120 in torch arch list: {any('120' in a for a in torch.cuda.get_arch_list())}")
if src != os.environ["EXPECT_SRC"]:
    raise SystemExit(f"  vllm imports from {src}, expected {os.environ['EXPECT_SRC']}")
if cap is None:
    raise SystemExit("  CUDA not available to torch")
EOF
) || die "Verification failed (see above)"
ok "compiled flash-attention kernels import"
ok "$(cd /tmp && "$VENV_DIR/bin/vllm" --version 2>/dev/null | tail -1) at $VENV_DIR/bin/vllm"

# ── 7. Optional: vllm-gguf-plugin ─────────────────────────────────────────────
if (( WITH_PLUGIN )); then
    section "vllm-gguf-plugin"
    [[ -d "$PLUGIN_SRC/.git" ]] || die "Plugin checkout not found at $PLUGIN_SRC (set PLUGIN_SRC)"
    TORCH_CUDA="$("$VPY" -c 'import torch; print(torch.version.cuda or "")')"
    CUDA_HOME_DIR=""
    # Prefer a system toolkit matching PyTorch's CUDA major.minor (e.g. /usr/local/cuda-13.0 for
    # torch cu130), then one with the same major, then the newest. Not the pip nvidia/cu13 folder:
    # its nvcc (13.4) and headers (13.0) disagree, which CCCL rejects (seen 2026-09-15).
    for d in "/usr/local/cuda-${TORCH_CUDA}" $(ls -d "/usr/local/cuda-${TORCH_CUDA%%.*}".* 2>/dev/null | sort -V -r) \
             $(ls -d /usr/local/cuda-[0-9]* 2>/dev/null | sort -V -r) /usr/local/cuda; do
        [[ -x "$d/bin/nvcc" ]] && { CUDA_HOME_DIR="$(realpath "$d")"; break; }
    done
    [[ -n "$CUDA_HOME_DIR" ]] || die "No CUDA toolkit (nvcc) under /usr/local/cuda*; the plugin compiles CUDA code"
    NVCC_VER="$("$CUDA_HOME_DIR/bin/nvcc" --version | grep -oP 'release \K[0-9]+\.[0-9]+')"
    info "PyTorch CUDA $TORCH_CUDA | nvcc $NVCC_VER ($CUDA_HOME_DIR)"
    if [[ "${TORCH_CUDA%%.*}" != "${NVCC_VER%%.*}" ]] && (( ! FORCE_PLUGIN )); then
        warn "CUDA major versions differ; PyTorch refuses to build extensions across that gap."
        warn "Skipping the plugin. Fix one of these, then rerun with --with-plugin:"
        info "  - install the CUDA ${TORCH_CUDA} toolkit (sudo apt install cuda-toolkit-${TORCH_CUDA/./-}), or"
        info "  - use a PyTorch built for CUDA ${NVCC_VER%%.*}.x in this venv (unverified for vLLM main)"
        info "  Or pass --force-plugin to try anyway."
    else
        if (( IN_PLACE )) || [[ "$(fs_type "$PLUGIN_SRC")" != "9p" ]]; then
            PLUGIN_INSTALL_SRC="$(realpath "$PLUGIN_SRC")"
        else
            sync_checkout "$(realpath "$PLUGIN_SRC")" "$PLUGIN_BUILD_SRC"
            PLUGIN_INSTALL_SRC="$PLUGIN_BUILD_SRC"
        fi
        # --no-build-isolation skips installing build deps, so install them (pyproject.toml pins).
        uv pip install --quiet --python "$VPY" "setuptools>=77.0.3,<81.0.0" wheel ninja
        info "Building the plugin's CUDA extension (this compiles; takes a while)"
        (cd "$PLUGIN_INSTALL_SRC" \
            && CUDA_HOME="$CUDA_HOME_DIR" PATH="$CUDA_HOME_DIR/bin:$VENV_DIR/bin:$PATH" \
               uv pip install --python "$VPY" --editable . --no-build-isolation) \
            || die "Plugin build failed (see the compiler output above)"
        "$VPY" -c 'import vllm_gguf_plugin' && ok "vllm_gguf_plugin imports"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
section "Next"
TORCH_CUDA_VER="$("$VPY" -c 'import torch; print(torch.version.cuda or "")')"
if [[ -x "/usr/local/cuda-$TORCH_CUDA_VER/bin/nvcc" ]]; then
    CUDA_HINT="export CUDA_HOME=/usr/local/cuda-$TORCH_CUDA_VER   # FlashInfer JIT: nvcc must match PyTorch's CUDA"
else
    CUDA_HINT="export VLLM_USE_FLASHINFER_SAMPLER=0   # no CUDA $TORCH_CUDA_VER toolkit: skip FlashInfer's JIT sampler
    # (proper fix: sudo apt install cuda-toolkit-${TORCH_CUDA_VER/./-}, then export CUDA_HOME=/usr/local/cuda-$TORCH_CUDA_VER)"
fi
cat <<EOF
  Before running vllm by hand (each of these was needed on this box, 2026-09-15):
    source $VENV_DIR/bin/activate        # puts the venv's ninja on PATH; FlashInfer JIT builds need it
    export HF_HUB_DISABLE_XET=1          # HF's Xet download backend stalls large downloads
    $CUDA_HINT
  (llm-test-bench sets HF_HUB_DISABLE_XET itself for servers it starts.)

  Run vllm from OUTSIDE $VLLM_SRC (e.g. cd ~ first). Inside it, vLLM's "python -m" helper
  subprocesses import that checkout's own vllm/ folder instead of $INSTALL_SRC and fail
  (ImportError about _vllm_fa2_C). A startup warning about VLLM_BIN is harmless.

  Point llm-test-bench at this vLLM (run.sh otherwise uses the old one in its .venv):
    export VLLM_BIN=$VENV_DIR/bin/vllm

  Smoke test by hand (test-plan-5060ti.md, B2):
    $VENV_DIR/bin/vllm serve Qwen/Qwen2.5-Coder-7B-Instruct-AWQ --max-model-len 8192 \\
      --gpu-memory-utilization 0.90 --enable-auto-tool-choice --tool-call-parser hermes --port 8000

  Through the harness (from llm-test-bench):
    VLLM_BIN=$VENV_DIR/bin/vllm ./run.sh --backend vllm --model-file models/16gb.vllm \\
      --models qwen2.5-coder:7b-awq --tasks python_safe_div
EOF
