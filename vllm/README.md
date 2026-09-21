# vLLM setup on a fresh Ubuntu box

Bring-up for an RTX 5060 Ti (Blackwell, `sm_120`) machine, from a clean Ubuntu 24.04 install to a
serving lane. `build-vllm.sh` here is the same script as the one in the vLLM checkout
(`my-build.sh`); this directory is the tracked copy, like `llamacpp/build-llama.sh`.

Everything below is either measured on this hardware or a documented upstream requirement. Where a
number came from a measurement, the date is given — re-check rather than trusting a stale figure.

## Git repos

```
vllm                origin    git@github.com:kjelloe/vllm.git
                    upstream  git@github.com:vllm-project/vllm.git
vllm-gguf-plugin    origin    https://github.com/vllm-project/vllm-gguf-plugin.git
```

The fork exists so local commits have somewhere to live; builds track `upstream/main`. The plugin
is only needed for **GGUF** models — skip it entirely if you serve AWQ/NVFP4/safetensors, which is
the recommended path on this card.

## Why build from source at all

`pip install vllm` gives you the last release. Two commits this card needs landed on `main`
afterwards: `13cf9e05c1` (prefer W4A4 NVFP4 kernels on SM120/121) and `f6326f53bd` (FlashInfer
Gated DeltaNet prefill on SM12x). `build-vllm.sh` installs from a checkout with
`VLLM_USE_PRECOMPILED=1`, so it downloads prebuilt kernels instead of compiling CUDA — minutes, not
hours, and no nvcc needed for vLLM itself.

## 1. System packages

```bash
sudo apt update && sudo apt install -y build-essential git curl python3.12-venv python3-pip
```

Driver: install the NVIDIA driver for a Blackwell card (580+; this box runs 591.86) and reboot.

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
```

## 2. CUDA toolkit 13.0 — needed for FlashInfer, not for vLLM

vLLM installs prebuilt, but **FlashInfer JIT-compiles its sampler at the end of every server
startup** and needs `nvcc` >= 12.9 to target SM120. Without it the server dies at the last moment
with a misleading `FlashInfer requires GPUs with sm75 or higher`.

```bash
sudo apt install -y cuda-toolkit-13-0
```

13.0 matches PyTorch's CUDA build. Do **not** point `CUDA_HOME` at the pip `nvidia/cu13` folder:
its nvcc is 13.4 while its headers are 13.0, and CCCL rejects the mismatch ("CUDA compiler and CUDA
toolkit headers are incompatible"). Every shell that starts a server needs:

```bash
export CUDA_HOME=/usr/local/cuda-13.0
```

## 3. Clone and build

```bash
git clone git@github.com:kjelloe/vllm.git ~/GIT/vllm
cd ~/GIT/vllm && git remote add upstream git@github.com:vllm-project/vllm.git
git fetch upstream && git merge upstream/main
```
```bash
git clone https://github.com/vllm-project/vllm-gguf-plugin.git ~/GIT/vllm-gguf-plugin   # GGUF only
```
```bash
VLLM_SRC=~/GIT/vllm ~/GIT/llm-test-bench/vllm/build-vllm.sh
```

**`VLLM_SRC` is required when running this copy of the script.** Its default is "the directory the
script lives in", which is true for `my-build.sh` inside the checkout but not for this tracked copy
— without it the script exits with `... is not a vLLM checkout`. Add `--with-plugin` for GGUF
support; it compiles a CUDA extension and needs PyTorch's CUDA major to match nvcc's.

The script creates `~/vllm-env` and (on WSL only) copies the checkout to ext4 first. On bare metal
that copy is pointless — pass `--in-place`. Useful flags: `--recreate-venv`, `--nightly`, `-h`.

## 4. Environment for every serving shell

```bash
export CUDA_HOME=/usr/local/cuda-13.0
export PATH="$HOME/vllm-env/bin:$PATH"     # FlashInfer calls `ninja` from here during warmup
export HF_HUB_DISABLE_XET=1                # Xet has stalled large downloads on these boxes
```

`PATH` is not optional for hand-started servers. Miss it and startup fails with
`FileNotFoundError: 'ninja'` — **after** the engine has already printed `GPU KV cache size` and the
memory profile, so a script that scrapes those lines appears to succeed while every server it
started is dying seconds later (cost a re-run on 2026-09-17). Activating the venv
(`source ~/vllm-env/bin/activate`) does the same job.

## 5. First model

AWQ or NVFP4 on stock vLLM, no plugin:

```bash
HF_HUB_DISABLE_XET=1 hf download cyankiwi/Qwen3.5-9B-AWQ-4bit
```
```bash
CUDA_HOME=/usr/local/cuda-13.0 ~/vllm-env/bin/vllm serve cyankiwi/Qwen3.5-9B-AWQ-4bit \
  --max-model-len 65536 --gpu-memory-utilization 0.92 --max-num-seqs 2 \
  --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 --limit-mm-per-prompt '{"image":0,"video":0}' \
  --host 127.0.0.1 --port 8000
```

This 9B is the pick for agentic work on 16 GB: its tool calls work with `tool_choice: "auto"`,
which the Qwen2.5-Coder 7B/14B builds do not (they emit `<tools>` instead of `<tool_call>`).
`--limit-mm-per-prompt` turns off the unused vision tower so it reserves no memory.

Expect, measured 2026-09-15/17 on one 5060 Ti: **7.55 GiB of weights, a 6.75 GiB KV pool =
209,615 tokens, ~56 tok/s per stream, ~2,700 tok/s prefill, 40 ms TTFT on short prompts.**

Confirm the two lines that matter:

```
GPU KV cache size: 209,615 tokens, Maximum concurrency for 65,536 tokens per request: 3.20x
Available KV cache memory: 6.75 GiB
```

## 6. Settings that matter, and why

| Setting | Value | Reason |
|---|---|---|
| `--gpu-memory-utilization` | 0.92 under WSL, 0.95 bare metal | Windows holds ~1.1 GiB of the display card, invisible to `nvidia-smi` inside WSL. Headless bare metal has no such tax. |
| `--max-num-seqs` | from client count | Measured 2026-09-17: costs ~0.5% of the KV pool, so set it for concurrency, not memory. See below. |
| `--max-model-len` | 65536 | Claude Code and Pi send ~20k tokens of prompt and tools per request. Prompt **plus** requested answer must fit. |
| `--enable-prefix-caching` | always | Agent clients resend an identical system prompt every turn; measured 95-96% hit rate in real traffic. |
| `kv-cache-dtype` | leave default | fp8 halves KV but is a precision risk; verify `python_hashmap` before trusting it on a 27B. |

**Concurrency** (measured, 12k-token prompts, cold cache): aggregate throughput doubles from one
client to two and then stops at the slot count. At 2 slots with 8 clients, half wait **46 s** for a
first token and throughput actually falls; at 8 slots nobody queues (7.5 s median) but each stream
decodes at ~8 tok/s instead of ~30. Pick from how many clients you have: 2 for one or two clients
that want speed, 4 as a burst hedge, 8 only if breadth beats per-client latency.

**Thinking** is on by default for this model and is not free: the same question answered in 4 tokens
with `--default-chat-template-kwargs '{"enable_thinking": false}'` versus 300 tokens of reasoning
and no answer at all without it (a 300-token budget ran out mid-thought). Leave it on for coding
quality; turn it off if clients send small `max_tokens`.

## 7. Sizing a box for this

Measured component sizes, 2026-09-17:

| Component | Size |
|---|---|
| Ubuntu 24.04 server (desktop ~15 GB) | ~5 GB |
| NVIDIA driver | ~1.5 GB |
| CUDA toolkit 13.0 | 4.9 GB |
| `~/vllm-env` (vLLM + PyTorch) | 7.0 GB |
| Model weights (9B AWQ / 27B NVFP4) | 8.5 / 20.6 GB |
| **Working total** | **~30-41 GB** |

256 GB of NVMe covers one job; 1 TB is the sane buy once you keep several models (the HF cache
reached 42 GB here without trying, and `hf download` wants 2-3x a model's size free while writing).

**RAM: 16 GB works, 32 GB recommended.** vLLM measured 1.7 GiB (API server) + 2.7 GiB (EngineCore)
at `tp=1`; add a worker process per extra GPU. Weights stream disk-to-VRAM, so host RAM is not a
staging area. 96 GB is only needed for llama.cpp's NVMe expert paging, not for this.

**PCIe 5 NVMe is overkill.** vLLM reads the model once, sequentially: 20.6 GB is ~4 s on PCIe 4 vs
~2 s on PCIe 5, against tens of seconds of engine init. Random-read performance is irrelevant —
nothing is paged during inference.

## 8. Verify like it is production

Point `llm-service-provider` at it rather than trusting curl:

```bash
cd ~/GIT/llm-service-provider && bin/llmctl smoke && bin/llmctl selftest
```

`smoke` is 9/9 when each lane answers messages, streaming, forced `tool_use` and `count_tokens`;
`selftest` runs a real Claude Code task per lane and checks the files it wrote actually pass
`node --test`.

## Gotchas

- **Never run `vllm serve` from inside the vLLM checkout.** Its `python -m` subprocesses import
  that tree's `vllm/` package and fail on stale `.so` files (`ImportError: _vllm_fa2_C`). Run from
  `~` or anywhere else.
- **`/proc/<pid>/environ` lies for vLLM processes** — `setproctitle` overwrites the start of the
  block, so variables look missing when they are not.
- **Comparing two configurations requires an idle GPU.** vLLM sizes its KV pool from free VRAM at
  startup, so a server started while the previous one is still releasing memory reports a smaller
  pool. This produced a bogus "raising `--max-num-seqs` costs 26% of KV" conclusion on 2026-09-16;
  gated re-measurement showed 0.5%. Wait for `nvidia-smi` to read idle between runs.
- **WSL only:** `curl` to `127.0.0.1` hangs for a server bound to `0.0.0.0` under mirrored
  networking — bind `--host 127.0.0.1` or use the box's address. Bare metal is unaffected.
- **WSL only:** pinned memory is off by default; `VLLM_WSL2_ENABLE_PIN_MEMORY=1` enables it on
  kernels >= 4.19.121.

## Where to go next

- `../vllm-plan.md` — the single-card bring-up this box actually followed, with results.
- `../test-plan-5060ti.md` — full test plan including the troubleshooting log.
- `../models/16gb.vllm`, `../models/2x16gb.vllm` — model entries for the harness.
- `~/GIT/llm-service-provider/upgrade-dual-5060.md` — second card, `tp=2`, capacity and sizing.
