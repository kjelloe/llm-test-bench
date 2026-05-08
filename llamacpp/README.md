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
3. Build with `-DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release -j$(nproc)`
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

## Troubleshooting

| Error | Fix |
|---|---|
| `Unsupported gpu architecture 'compute_120a'` | Upgrade to CUDA 12.8+ (see above) |
| `llama-server binary not found on PATH` | Set `export LLAMA_SERVER_BIN=~/GIT/llama.cpp/build/bin/llama-server` |
| `LLAMA_MODELS_DIR not set` | `export LLAMA_MODELS_DIR=/path/to/gguf` |
| `GGUF file not found` | Run `./fetch-hf.sh` to download, or check `models/default.txt` GGUF paths |
| OpenSSL warning during cmake | Harmless — HTTPS is disabled but local serving is unaffected |
