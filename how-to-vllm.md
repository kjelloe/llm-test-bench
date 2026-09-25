# How to Continue the vLLM Experiment on RTX 50xx (Blackwell)

Context: this repo's own rig is RTX 4090 + 2×RTX 3090 (Ada/Ampere, compute capability 8.9/8.6).
Neither vLLM core nor the `vllm-gguf-plugin` require Blackwell — that was confirmed directly from
source (`CMakeLists.txt` lists 8.6/8.9 as fully supported, and a plugin fix titled "remove
Blackwell bf16 restriction" turned out to be *unlocking* Blackwell to match a path Ampere/Hopper
already had, not gating anything to it). So the new RTX 50xx box isn't required infrastructure —
it's just where the vLLM experiment is now actually running. Full background: `CLAUDE.md`'s
"vLLM backend constraints" section (`~/GIT/llm-test-bench/CLAUDE.md`) and `next-runs.md`.

## 1. Setup checklist

- Install vLLM (`uv pip install vllm --torch-backend=auto` or plain `pip`). Prefer a recent
  version — Blackwell support in both vLLM and the plugin has been actively evolving upstream.
- Install `vllm-gguf-plugin` from source, editable, against the same PyTorch vLLM uses:
  ```bash
  git clone https://github.com/vllm-project/vllm-gguf-plugin
  cd vllm-gguf-plugin
  uv pip install -e . --no-build-isolation
  ```
  The current checkout (`d4c1f0d`, 2026-08-31, still the latest upstream on 2026-09-15) already
  includes the Blackwell bf16 fix (`bb5d952`) and the 27B load-OOM fix (`51b8d7a`). It needs a
  vLLM from after the June 2026 GGUF move: the repo's `.venv` has vLLM 0.21.0 (May 2026), which
  is too old. Use a fresh venv on WSL ext4 with vLLM from upstream `main` installed with `VLLM_USE_PRECOMPILED=1` (two SM120 speedups
  landed after the 0.29.0 release: `13cf9e05c1` and `f6326f53bd`). `/mnt/c/GIT/vllm/my-build.sh`
  automates the install and verifies it; see
  `test-plan-5060ti.md`.
- Install the CUDA 13.0 toolkit (`cuda-toolkit-13-0`) and set `CUDA_HOME=/usr/local/cuda-13.0` in
  every shell that runs `vllm serve` (and before `./run.sh --backend vllm`). FlashInfer JIT-compiles
  kernels at startup and needs nvcc >= 12.9 for SM120, matching PyTorch's CUDA 13.0. The pip
  `nvidia/cu13` nvcc does not work (13.4 compiler, 13.0 headers). Without it vLLM logs `SM 12.x
  requires CUDA >= 12.9` and then dies with the misleading `FlashInfer requires GPUs with sm75 or
  higher`. Check `echo $CUDA_HOME`: a `~/.bashrc` that puts an older CUDA on PATH is not enough.
- Under WSL keep `--gpu-memory-utilization` at 0.92 or lower: Windows holds ~1.1 GiB of the card,
  which `nvidia-smi` inside WSL doesn't show. The real free memory: `torch.cuda.mem_get_info()`.
- Verify the GPU is actually recognized before doing anything else:
  ```bash
  nvidia-smi --query-gpu=index,name,compute_cap,memory.total --format=csv
  ```
  Blackwell should report compute capability 12.0 (e.g. RTX 5070 Ti and similar RTX 50-series
  parts). If CUDA/driver isn't picking the card up correctly, nothing below will work — confirm
  this first.
- **`./run.sh` failing with `error: externally-managed-environment` (2026-09-24, hit on this
  box):** Debian-family distros create a `.venv` *without pip* unless `python3-pip`/`python3-full`
  is installed at the OS level — `python3 -m venv .venv` succeeds structurally, but a bare `pip`
  call then falls through `PATH` to the system pip, which refuses (PEP 668). Fix:
  `sudo apt install python3-full python3-pip; rm -rf .venv` and re-run. `run.sh` itself was also
  hardened (`"$VENV/bin/python3" -m pip install ...` instead of a bare `pip`) so a repeat gives a
  clearer `No module named pip` instead of the confusing externally-managed error.
- **`VLLM_BIN` must prefix the exact same command as `./run.sh`**, on one line —
  `VLLM_BIN=~/vllm-env/bin/vllm ./run.sh --backend vllm ...`. Setting it as its own statement
  (`VLLM_BIN=... && ./run.sh ...` counts, but `VLLM_BIN=...` alone on a line before `./run.sh` on
  the next does not) leaves it unexported, and `run.sh` — a new process — never sees it.

## 2. Models to download

Same two picks already recommended in `CLAUDE.md`, chosen for architecture-confidence (Qwen 2.5
is explicitly in the plugin's own "Tested model coverage" table) rather than raw benchmark score —
a model that won't load is worth nothing, and most of this repo's actual highest-scoring
small/mid models are MXFP4 format, which doesn't appear in that table at all (real, untested
load risk, independent of which GPU generation you're on).

- **16 GB single GPU**: `qwen2.5-coder:14b`
  hf: `bartowski/Qwen2.5-Coder-14B-Instruct-GGUF`, Q4_K_M, ~9 GB weights.
- **2× 16 GB (32 GB, tp=2)**: `qwen2.5-coder:32b-q4`
  hf: `bartowski/Qwen2.5-Coder-32B-Instruct-GGUF`, Q4_K_M, ~18.5 GB weights — PERFECT 19/19
  coding on this repo's llama-server benchmark, the strongest coder tested here.

Download with `huggingface-cli download <repo> <quant-file>.gguf --local-dir <dir>`, or
whatever download flow the box already uses.

## 3. Launch

```bash
# 16 GB single GPU
vllm serve bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q4_K_M --tokenizer Qwen/Qwen2.5-Coder-14B-Instruct

# 2×16 GB, tensor parallel
vllm serve bartowski/Qwen2.5-Coder-32B-Instruct-GGUF:Q4_K_M --tokenizer Qwen/Qwen2.5-Coder-32B-Instruct \
  --tensor-parallel-size 2
```

No `--quantization gguf` patch flag needed for this `repo:quant` form: GGUF support now lives in
the plugin, not in-tree. (The harness serves a local file instead and still passes
`--quantization gguf`; with the plugin installed, that name maps to the plugin's GGUF method.) Both of these are plain dense Qwen2.5 checkpoints, so none of
the MoE-specific plugin quirks apply (K-quant-vs-I-Matrix kernel selection, `--hf-config-path`
for Qwen3.5-MoE) — those only matter once you branch out past this pair.

## 4. Smoke test

```bash
curl -s http://127.0.0.1:8000/v1/completions \
  -H 'content-type: application/json' \
  -d '{"model":"bartowski/Qwen2.5-Coder-14B-Instruct-GGUF","prompt":"def fib(n):","max_tokens":32}'
```

Expect a real completion, not an error. (If it says the model isn't found, check the served name
with `curl -s http://127.0.0.1:8000/v1/models`.) If this repo (`llm-test-bench`) is cloned onto
the same box, its own harness can drive the full task suite instead of a manual curl. Two things
to know first: `lib/vllm_client.py` always **spawns and manages its own `vllm serve` subprocess
locally**, with no remote-host mode, so this only works run directly on the RTX 50xx machine; and
in GGUF mode it serves a **local file** with `--tokenizer <hf:> --quantization gguf`. So a `.vllm`
GGUF entry's `hf:` must be the original model repo that holds the tokenizer (e.g.
`Qwen/Qwen2.5-Coder-14B-Instruct`, as in `32gb.vllm`, `2x24gb.vllm`, `default.vllm`,
`16gb.vllm` and `2x16gb.vllm`), not bartowski's GGUF-only repo, and the GGUF itself is downloaded
separately through a `models/*.txt` entry. Point `VLLM_BIN` at the new vLLM's binary, or `run.sh`
uses the old vLLM in the repo's `.venv`. Step-by-step: `test-plan-5060ti.md`.

Under WSL mirrored networking, `curl` to `127.0.0.1` hangs for a `vllm serve` bound to `0.0.0.0`
(its default); use the machine's address, or start vLLM with `--host 127.0.0.1`. For agentic use
(tool calls, Claude Code), the tested 16 GB pick is `cyankiwi/Qwen3.5-9B-AWQ-4bit`, not the
Qwen2.5-Coder models, whose tool calls fail with `tool_choice: "auto"`: see `vllm-plan.md`.

## 5. What to record

- Did it load cleanly? (Expected: yes, for both — this is the whole point of the
  architecture-confidence pick.)
- Speed vs. this rig's llama-server baseline for the same weight class: `qwen2.5-coder:32b-q4`
  scores 28/33 at 36.5 tok/s on llama-server here (2×24 GB, PERFECT 19/19 coding) — a useful
  reference point, not a claim that vLLM should match it (the historical 2026-07-06 vLLM-vs-
  llama-server comparison on this rig showed vLLM ~4× slower single-request, for a different
  model/quant combo — worth re-establishing whether that gap holds on Blackwell or was partly an
  Ada/Ampere-specific artifact).
- Any load errors, especially anything Blackwell-specific (this is the first real Blackwell test
  for anything in this project) — capture the exact error text before treating it as a dead end.

## 6. Also worth trying on this hardware, separately from vLLM

Two llama.cpp forks were previously shelved on this rig specifically *because* they need
Blackwell:
- `RaymondHuang210129/llama.cpp-adaptive-kv-streaming` — KV-cache streaming for `qwen3.8:27b`
  long-context on small VRAM; crashes reliably on Ada/Ampere, author validated only on RTX 5070 Ti.
- `ik_llama.cpp`'s MTP speculative decoding for `qwen3.8-flash-next` — a community report of
  ~90 tok/s on a single RTX 5090 was never reproduced on this rig's 3-way Ada/Ampere split;
  plausibly a genuine Blackwell bandwidth + no-cross-GPU-overhead advantage.

Out of scope for this vLLM box specifically, but if the same machine (or another RTX 50xx box)
ever runs llama.cpp too, both are worth a look — see `project_adaptive_kv_streaming_fork` memory
and the `qwen3.8-flash-next` section of `models/candidates.txt` for full context.

**A third one, and this one this box's own hardware (96 GB DRAM + RTX 5060 Ti ×2) directly
qualifies for**: a Reddit tip for `qwen3.8-flash-next` — "if you have >=16GB vram and 64-96GB
Ram, run qwen3.8 flash next, stream ngrams off ssd and offload experts to cpu" — turned out to
map to two real, confirmed-in-source llama.cpp mechanisms rather than folk wisdom:

1. The model's huge N-gram Embedding table (`per_layer_token_embd` tensor) is created with the
   `TENSOR_READ_LAZY` flag in `qwen4exp.cpp` — rows are paged in from the mmap'd GGUF on demand
   instead of the whole table being read at load time. Requires mmap enabled (this repo's
   `qwen3.8-flash-next` config already satisfies that — no `no_mmap` set).
2. "Offload experts to CPU" is this repo's own already-documented `-ngl 999 --n-cpu-moe N
   --no-repack` technique (see `CLAUDE.md`'s CPU-MoE paging note).

**Recipe to try** (skip `--fit`, restrict to the GPUs you actually have):
```bash
CUDA_VISIBLE_DEVICES=0,1 llama-server -m Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf \
  -ngl 999 --n-cpu-moe N --no-repack --cache-type-k f16 --cache-type-v f16 --flash-attn \
  --batch-size 1024 --ubatch-size 512
```
`N` is unknown up front — this model is ~106 GB (UD-Q4_K_XL) against a 32 GB VRAM budget, a much
bigger gap than the "~30% of MoE layers for a 3 GB overage" rule this repo learned from
`gpt-oss-120b` — expect to need most MoE layers CPU-offloaded, found by trial. Speed is also
genuinely unknown: 6B activated params/token is in the same tier as models this repo has a rough
RAM-bandwidth speed rule for (~53 tok/s / ~10 tok/s on 86 GB DDR5 at ~90 GB/s for A3B/A15B), but
this model's much larger total footprint pulling from RAM every token could behave differently.
Don't assume a win or a loss — this is a real test, not a foregone conclusion. Full detail in
`next-runs.md`'s "qwen3.8-flash-next stream ngrams" section.

**Result (2026-09-14/15): it works.** On one RTX 5060 Ti with 88 GB of WSL RAM, the full run
scored 37/38 eligible tasks at 18.1 tok/s. The working config is not the recipe above: keep
`--fit on --fit-target 512` (it moves the experts to the CPU by itself) and add `--no-repack`. No
`CUDA_VISIBLE_DEVICES` or `--n-cpu-moe N` needed. Steps: [`how-to-test-flash-next.md`](how-to-test-flash-next.md).
Results: the `qwen3.8-flash-next-16gb` entry in `models/candidates.txt`.

## 6b. Second experiment on this box: Qwen3.8-27B via vLLM-native quants

Once §1-5 confirm the box works at all (the Qwen2.5-coder pair above), the more interesting test
is `Qwen3.8-27B` — architecturally identical to this repo's own extensively-tested `qwen3.8:27b`
(Gated DeltaNet hybrid, confirmed via `config.json`: `Qwen3_5ForConditionalGeneration` /
`qwen3_5`), but tried here in vLLM-native quant formats instead of GGUF. For 2×16 GB:

- **✅ CONFIRMED 2026-09-24/25, this was the right pick**: `QUASAR-QAT/Qwen3.8-27B-QUASAR-NVFP4`
  (20.6 GB, native Blackwell NVFP4 acceleration) — **27/28 effective coding pass, `python_hashmap`
  passes despite 4-bit activations, ~32 tok/s, context clean through 128k.** `node_paratrooper`
  (L6-full) borderline (1/7) — the same cross-GPU tensor-split fragility already confirmed on
  this model's llama.cpp side, now confirmed on vLLM's `tp=2` too. Full writeup:
  `reports/models-status-Sept-2026.md`'s dedicated vLLM section. `models/2x16gb.vllm` now has
  the confirmed-working entry (`qwen3.8-27b:nvfp4-next`, dropped `enforce_eager`, added
  `language_model_only` + `max_num_seqs=4`).
- **Not tried, no longer needed**: `unsloth/Qwen3.8-27B-NVFP4` (23.4 GB, VL-capable fallback) —
  the primary pick worked, so this backup was never exercised.
- Skip `Qwen/Qwen3.8-27B-FP8` (official, 30.9 GB) for this VRAM budget — leaves ~1 GB across the
  whole 32 GB, no real context room; that one wants a single 32 GB+ card instead.

None of these are GGUF — plain `vllm serve <repo>` works directly, no plugin needed (the GGUF
plugin only matters for the GGUF path in §1-5). Full rationale, sizes, and the source of this
lead (a Reddit thread) in `next-runs.md`'s "Reddit-sourced vLLM-native Qwen3.8-27B quant leads"
section.

**Resolved**: multiple people in that Reddit thread claimed vLLM flatly doesn't support GGUF —
that claim was about GGUF specifically, and this confirmed result doesn't test that (NVFP4 is a
different, non-GGUF loading path); this repo's own source-verified `vllm-gguf-plugin` finding
from §1-5 remains the actual answer on the GGUF question, still not independently re-benchmarked
here since the plugin migration.

## 6c. Model files for this box (added 2026-09-14)

Runnable entries for §4/§6b are now in `models/16gb.vllm` (single-card smoke test, usable with
just RTX 5060 Ti #1) and `models/2x16gb.vllm` (the QUASAR-QAT NVFP4 tp=2 config from §6b, plus a
dense-Qwen2.5 fallback — not runnable until the second 5060 Ti is installed). Don't run
`fetch-hf.sh` on the `.vllm` files: their `hf:` fields name the original model repos, which the
harness passes as `--tokenizer` (the plugin's own README does the same), and those repos contain
no GGUF. Download each GGUF through its `models/*.txt` entry instead (noted in each file). The
NVFP4 entry downloads itself from the Hub on the first `vllm serve`. Step-by-step:
`test-plan-5060ti.md` for the benchmark half, and
`~/GIT/llm-service-provider/upgrade-dual-5060.md` for the whole second-card upgrade (hardware
checks, switching the serving lane to tp=2, how many users 32 GB serves, DDR5 sizing, rollback).

A fresh 2026-09-14 web check for this addition turned up **inconsistent, partly unreliable**
results for "the" Qwen3.8-27B NVFP4 repo (sizes claimed anywhere from 14-23 GB for what should be
the same 4-bit weights, plus repeated mentions of a "NInfer" proprietary runtime that reads as
low-quality SEO content, not verified fact). Stuck with the QUASAR-QAT pick this section already
named before that search, since it's independently corroborated at ~19.7-20.6 GB and was chosen
for a documented reason (best VRAM headroom, `vllm`-tagged) rather than search-result noise.
**Update 2026-09-24/25: it paid off — see the CONFIRMED result above.** The repo, size, and pick
rationale all held up; the caution below is now historical (kept for context on how the pick was
made, not because the result is still unverified): originally, verify the repo/file actually
exists and re-check its real size on huggingface.co before downloading, since the comment block
in `2x16gb.vllm` wasn't yet CONFIRMED the way the rest of this project's dated findings are.

Also resolved in that same check: **`qwen3.8-flash-next` (already in `models/candidates.txt` for
llama-server) is NOT a realistic vLLM target on this box at all**, regardless of how many 5060
Tis get added. vLLM's own official recipe for that architecture (qwen4exp, landed in vLLM main
2026-09) budgets ~250 GB aggregate VRAM (validated minimum 2× GB300, 4× recommended) — orders of
magnitude past what a 5060 Ti box can reach. (Since `3116c5d06b`, 2026-09-09, vLLM can keep the
n-gram table in pinned host RAM with `--engram-config '{"cpu_offload": true}'`, but the 125B main
model still needs far more than 32 GB of VRAM. On a WSL2 box it can't work at all: vLLM turns pinned
memory off under WSL.) If Flash-Next itself (not just the 27B dense model)
is ever wanted on this hardware, the realistic path is llama.cpp's CPU-MoE-offload technique
(§6's "stream ngrams off ssd and offload experts to cpu" recipe), not vLLM. That path has since
been confirmed on one RTX 5060 Ti: 37/38 eligible tasks at 18.1 tok/s (see §6).

## 7. Once there are results

Cascade findings back into `CLAUDE.md` (replace the "not yet vLLM-tested" caveat on the
recommendation), `next-runs.md`, and memory — same pattern used for every other finding in this
project.
