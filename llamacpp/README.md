# llamacpp — build helpers

Scripts for building llama.cpp with CUDA support on Ubuntu.

## Prerequisites

### 1. Clone llama.cpp

Clone the repo next to `ollama-code-bench` (or anywhere — the script auto-detects):

```bash
git clone https://github.com/ggerganov/llama.cpp ~/GIT/llama.cpp
```

Or override the path:

```bash
export LLAMA_SRC_DIR=/path/to/llama.cpp
```

### 2. CUDA 12.8+ (required for Blackwell GPUs — RTX 5000 series)

The RTX 5060 Ti and other Blackwell GPUs use compute capability `sm_120a`. CUDA 12.0 and earlier **cannot compile for this architecture** — nvcc will hard-fail with:

```
nvcc fatal : Unsupported gpu architecture 'compute_120a'
```

You need CUDA 12.8 or newer. Install on Ubuntu 24.04:

```bash
# Add NVIDIA's package repo
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install cuda-toolkit-12-8

# Add to PATH (also add these lines to ~/.bashrc for persistence)
export PATH=/usr/local/cuda-12.8/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH

# Verify
nvcc --version   # should print: release 12.8, ...
```

> **Ubuntu 22.04?** Replace `ubuntu2404` with `ubuntu2204` in the URL above.

---

## Build

```bash
# From the ollama-code-bench root:
./llamacpp/build-llama.sh
```

The script will:
1. Detect Ubuntu and CUDA versions — block if CUDA < 12.8 on a Blackwell GPU
2. Check and install missing packages (`cmake`, `build-essential`, `libcurl4-openssl-dev`)
3. Build with `-DGGML_CUDA=ON -DGGML_CUDA_GRAPHS=ON -DCMAKE_BUILD_TYPE=Release -j$(nproc)`
   (`GGML_CUDA_GRAPHS` added 2026-09-04 — required for the `GGML_CUDA_GRAPH_OPT=1` runtime env
   var to do anything at all; it's OFF by default upstream and the env var is a silent no-op
   without it. See the qwen4exp row below before relying on this for multi-GPU speed, though —
   it measured *worse*, not better, on this rig's 3-GPU `--fit` setup.)
4. Verify `llama-server` binary and print its version
5. Prompt to install `llama-server` to `/usr/local/bin`
6. Prompt to install an optional systemd service with MoE-optimised flags

If a previous build failed (e.g. due to wrong CUDA), clean first:

```bash
rm -rf ~/GIT/llama.cpp/build
./llamacpp/build-llama.sh
```

---

## Use with ollama-code-bench

After a successful build:

```bash
# If you chose not to install to /usr/local/bin, point to the local binary:
export LLAMA_SERVER_BIN=~/GIT/llama.cpp/build/bin/llama-server

# Set the GGUF model directory
export LLAMA_MODELS_DIR=/path/to/gguf/models

# Run the benchmark with the llama-server backend
./compare.sh --backend llama-server

# Compare against a previous ollama run
./compare-results.sh output/results-compare.json output/results-compare-ls.json
```

---

---

## Architecture minimum-commit requirements

Some model architectures require a specific minimum llama.cpp commit. Building from the latest `master` is always safe; older checkouts may fail with `unknown model architecture: '<name>'`.

| Architecture | Model | Min commit | PR |
|---|---|---|---|
| `mellum` | JetBrains Mellum2-12B-A2.5B | `4fb16eccc` | #23966 |
| Gated DeltaNet hybrid | qwen3.8:27b | `0d0bfcd4f` (qwen35.cpp merge, ≥ 2026-08-13) | — |
| `qwen4exp` (Gated DeltaNet+QSA hybrid) | qwen3.8-flash-next | `6c84c7d5d` (PR #27742, native support) minimum; **pin to `67a17c17c` for correct speed** | #27742, #27880 |

If you see `error loading model: unknown model architecture: 'mellum'` (or `qwen4exp`, or the
DeltaNet arch name), update and rebuild:

```bash
cd ~/GIT/llama.cpp
git pull
cmake --build build --config Release -j$(nproc)
```

**⚠ For `qwen4exp` (qwen3.8-flash-next) specifically, do NOT just build latest `master`.**
Confirmed 2026-09-04: mainline commit `49c0dc82b` (82 commits past `67a17c17c`) is a real
regression — 27–55% slower on longer-generation tasks than `67a17c17c`, and a newer multi-GPU
CUDA-graph optimization (`GGML_CUDA_GRAPH_OPT=1`) measured *worse* on this rig's topology, not
better. This architecture is under fast-moving, non-monotonic upstream development — **checkout
`67a17c17c` explicitly** (`git checkout 67a17c17c` before building) rather than `master`, and
re-verify speed on a 3-task comparison (`python_hashmap`, `python_expr_eval`,
`python_safe_div`) before trusting any newer commit for this model. Full history in this repo's
`CLAUDE.md` and `next-runs.md`.

---

## Dual-GPU setup (llama-server)

For llama-server on two GPUs, llama.cpp uses `--tensor-split` for dense models and `--n-gpu-layers 999` for MoE models (expert routing handles distribution automatically). For the benchmark harness, add `tensor_split=1|1` (pipe-separated — the harness converts `|` to `,` for the flag) to the model params in the `.txt` model file.

Most dual-GPU work in this repo uses **vLLM** (`tp=2`) since it handles tensor parallelism more reliably for large GGUFs. See `models/2x24gb.vllm` for the ready-to-run dual-GPU model set:

```bash
export LLAMA_MODELS_DIR=/path/to/gguf/models
./compare.sh --backend vllm --model-file models/2x24gb.vllm
```

Models pre-configured for dual 24 GB GPUs (48 GB total): `llama3.3:70b`, `qwq:32b`, `qwen2.5-coder:32b`, `qwen3-coder-next` (commented until GONE repo resolved), `qwen3-coder-480b` (commented until vLLM MoE GGUF fix lands).

**HF_TOKEN required** for `llama3.3:70b` (gated meta-llama repo). Populate `hf-token.txt` in the repo root or set `HF_TOKEN` in your environment.

---

## Replicating on a new machine — checklist

1. **Clone repos:**
   ```bash
   git clone https://github.com/ggerganov/llama.cpp ~/GIT/llama.cpp
   git clone <this-repo> ~/GIT/ollama-code-bench
   ```

2. **Build llama.cpp** (CUDA support, Ampere/Ada/Blackwell):
   ```bash
   cd ~/GIT/ollama-code-bench
   ./llamacpp/build-llama.sh
   ```

3. **Set environment variables** (add to `~/.bashrc`):
   ```bash
   export LLAMA_SERVER_BIN=~/GIT/llama.cpp/build/bin/llama-server
   export LLAMA_MODELS_DIR=/path/to/gguf/models
   export HF_TOKEN=hf_...          # needed for llama3.3:70b and other gated models
   ```
   Or populate `hf-token.txt` in the repo root instead of `HF_TOKEN`.

4. **Install Python/Node/dotnet dependencies:**
   ```bash
   ./install.sh
   ./preflight.sh   # verify everything
   ```

5. **Download GGUFs** (models with live HF repos):
   ```bash
   ./fetch-hf.sh models/default.txt
   ./fetch-hf.sh models/2x24gb.vllm   # for dual-GPU models
   ```

6. **⚠ Copy GONE GGUFs manually** — these HF repos no longer exist; files must be
   transferred from the original machine (e.g. via `rsync` or external drive):

   | Model | File | Used in |
   |---|---|---|
   | `noctrex-qwen3.6:35b` | `Qwen3.6-35B-A3B-MTP-MXFP4_MOE.gguf` | `default.txt` |
   | `qwen3-coder:30b-1m` | `Qwen3-Coder-30B-A3B-Instruct-1M-Q4_K_M.gguf` | `default.txt` |
   | `gemma4:26b` | `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` | `default.txt` |
   | `qwen3-coder-next` | `Qwen3-Coder-Next-Q4_K_M-0000{1-4}-of-00004.gguf` | `experimental.txt` |
   | `gemma4:31b` | `gemma-4-31B-it-Q4_K_M.gguf` | `experimental.txt` |
   | `qwen3.8:27b` (original) | `Qwen3.8-27B-Q4_K_M.gguf` | `24gb.txt`, `2x24gb.txt` — **⚠ genuinely irreplaceable**: this exact file is the *only* build (of 6 independently tested, across every GPU config) confirmed to pass `node_paratrooper` on both single-GPU and 3-GPU. Deleted upstream 2026-08-19; do not delete the local copy. If you don't have it, use `bartowski`'s `Qwen3.8-27B-Q5_K_M.gguf` instead (single-GPU only, see `CLAUDE.md`) |
   | `ornith:1.5-9b` | `Ornith-1.5-9B-MXFP4_Q8_0-Imatrix.gguf` | `12gb.txt`, `16gb.txt` — deleted upstream as of the 2026-08-30 scout |
   | Qwen3.8-Flash-Next MTP companion | `Qwen3.8-Flash-Next-MTP-Q4_K_M.gguf` (store at `allmodels/MTP/`) | `qwen3.8-flash-next-ikllama` in `candidates.txt` (ik_llama.cpp `-md` flag) — source repo `dzannotti/Qwen3.8-Flash-Next-MTP-GGUF` went GONE per scout |
   | `qwen2.5-coder:32b-q4` / `qwen2.5-coder:32b` | `Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf` (Q5_K_M also referenced, less critical) | `24gb.txt`, `2x24gb.txt`, `3x24gb.txt` — the strongest coder in this whole benchmark (PERFECT 19/19). Source repo `bartowski/Qwen2.5-Coder-32B-Instruct-GGUF` went GONE per the 2026-09-06 scout; only the Q4_K_M file is confirmed safe on the original machine — the Q5_K_M variant was never downloaded there and can no longer be fetched fresh from this repo |

   Transfer command (from old machine):
   ```bash
   rsync -avP /path/to/llama_models/*.gguf newmachine:/path/to/llama_models/
   ```

7. **Run the canonical benchmark:**
   ```bash
   ./compare.sh --backend llama-server   # single GPU (default.txt)
   ./compare.sh --backend vllm --model-file models/2x24gb.vllm   # dual GPU
   ```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `Unsupported gpu architecture 'compute_120a'` | Upgrade to CUDA 12.8+ (see above) |
| `unknown model architecture: 'mellum'` | `git pull && cmake --build build -j$(nproc)` in llama.cpp |
| `llama-server binary not found on PATH` | Set `export LLAMA_SERVER_BIN=~/GIT/llama.cpp/build/bin/llama-server` |
| `LLAMA_MODELS_DIR not set` | `export LLAMA_MODELS_DIR=/path/to/gguf` |
| `GGUF file not found` | Run `./fetch-hf.sh` for live repos; copy manually for GONE repos (see table above) |
| OpenSSL warning during cmake | Harmless — HTTPS is disabled but local serving is unaffected |
| `llama-server exited unexpectedly` with wrong model running | `_kill_port_occupant` fix is in `lib/llama_server_client.py` — stale server on port 8080 is evicted automatically since 2026-06-07 |
