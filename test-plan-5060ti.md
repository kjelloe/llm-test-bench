# Test Plan: RTX 5060 Ti Box — qwen3.8-27b-gsqrco and vLLM

Box: 1× RTX 5060 Ti 16 GB (Blackwell, sm_120), Ryzen 7 9800X3D, WSL2 with ~86 GB RAM visible. A
second 5060 Ti is coming, via PCIe bifurcation. Facts marked "checked 2026-09-15" were verified on
this box that day. Part B folds in a vLLM setup checklist from a helper's notes (2026-09-15).

Baseline already on this box: `qwen3.8-flash-next-16gb` on llama-server, 37/38 eligible tasks at
18.1 tok/s (see `models/candidates.txt`).

## Part A — qwen3.8-27b-gsqrco on llama-server

Why: the best GGUF that fits entirely in 16 GB (11.8 GB). It scored 9/10 on the spot check on an
RTX 4090 at ~55 tok/s, but has never run on this card. It's the fast alternative to Flash-Next.

**A1. Move the file onto WSL's filesystem.** Checked 2026-09-15: it's still on `/mnt/c` (9p).
```bash
mv /mnt/c/GIT/llm-test-bench/llama_models/Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf ~/models/
export LLAMA_MODELS_DIR=~/models LLAMA_SERVER_BIN=~/GIT/llama.cpp/build/bin/llama-server
```
The pinned llama.cpp `67a17c17c` is new enough (this model family needs a build from 2026-08-13 or
later).

**A2. Smoke test.**
```bash
./run.sh --model-file models/16gb.txt --models qwen3.8-27b-gsqrco --backend llama-server --tasks python_safe_div
```
The entry uses `no_mmap`, so expect a harmless "`--no-mmap` is deprecated" warning. The whole model
sits in VRAM, so nothing pages from disk. Expected speed is roughly 24 tok/s, an estimate from the
card's memory bandwidth (448 GB/s vs ~1008 GB/s on the 4090), not a measurement.

**A3. Spot check.**
```bash
TASKS=python_safe_div,node_slugify,python_lru_cache,csv_nordic_property,node_csv_parser,python_tokenizer,python_expr_eval,python_hashmap,node_para_core,node_paratrooper
./run.sh --model-file models/16gb.txt --models qwen3.8-27b-gsqrco --backend llama-server --tasks $TASKS
```
Compare with the 4090: 9/10, with only `node_paratrooper` failing. Watch `python_hashmap`: it
needs the f16 KV cache the entry already sets.

**A4. Full run.** Same command without `--tasks`. The entry sets `max_ctx=32768`, so
`context_64k` and above are skipped. The multi-hop tasks (~29k-token prompts) still fit.

**A5. Optional: push the context limit.** This model keeps a KV cache in only 16 of its 64 layers,
about 16 KB per token at f16. 11.8 GB of weights plus 64k context (~1 GB) should fit; 128k
(~2.1 GB) is tight on 16 GB. Add a `candidates.txt` copy of the entry with `max_ctx=65536`, then
`131072`, and run `--task-group context`. Keep f16 KV throughout: with q8_0 this model family drops
`_EMPTY` in `python_hashmap`. For reference, qwen3.8:27b slowed to ~10 tok/s at 128k on a single
4090.

**A6. Record** the results under the entry in `models/16gb.txt` (and `candidates.txt`), and
compare speed and quality with `qwen3.8-flash-next-16gb`.

## Part B — vLLM

State checked 2026-09-15:
- **Install from `main`, not the 0.29.0 release.** `~/GIT/vllm` is now at upstream `main`
  `2c2cbd84fd` (2026-09-15). Two commits that matter for this card landed after 0.29.0 was cut:
  `13cf9e05c1` (prefer 4-bit weight+activation NVFP4 kernels on SM120/121) and `f6326f53bd`
  (FlashInfer Gated DeltaNet prefill on SM12x). `~/GIT/vllm/.venv` still holds a May build.
- **The GGUF plugin isn't installed anywhere.** Its checkout (`d4c1f0d`) is the latest upstream
  and has the Blackwell bf16 fix and the 27B load-OOM fix.
- **PyTorch here is CUDA 13.0, but `nvcc` is 12.8.** The plugin compiles a CUDA extension, and
  PyTorch normally refuses to build across a CUDA major-version gap. That's why the first smoke
  test below uses AWQ, which needs no plugin.
- **Both checkouts live on `/mnt/c` (9p).** Build from copies on WSL ext4.
- The harness picks `VLLM_BIN` first, then `vllm` on `PATH`; `run.sh` activates the repo's `.venv`.
- The harness only tests the BEGIN_FILE edit format. **It never exercises tool calling**, so the
  tool-call check in B3 is manual.

**B1. vLLM from `main`, prebuilt kernels, on ext4.** Leave the repo's `.venv` alone.
Automated: `/mnt/c/GIT/vllm/my-build.sh` does all of this (add `--with-plugin` for B5) and verifies
the result; it was used for the first successful build on 2026-09-15. The manual steps:
```bash
git clone /mnt/c/GIT/vllm ~/src/vllm           # local copy onto ext4; no network needed
uv venv ~/vllm-env --python 3.12 && source ~/vllm-env/bin/activate
cd ~/src/vllm && VLLM_USE_PRECOMPILED=1 uv pip install --editable . --torch-backend=auto
python -c "import vllm, torch; print(vllm.__version__, torch.version.cuda, torch.cuda.get_device_capability(0))"
# expect a main-branch dev version and (12, 0)
```
`VLLM_USE_PRECOMPILED=1` pulls prebuilt kernels for that commit instead of compiling (the
checkout's own install docs use this command). Fallback if that fails: `uv pip install vllm
--torch-backend=auto` (0.29.0, without the two SM120 commits).

**B2. Smoke test with stock vLLM (AWQ, no plugin), by hand.** Set these first; each was found the
hard way on 2026-09-15:
```bash
source ~/vllm-env/bin/activate   # puts ninja on PATH: FlashInfer compiles its sampler at startup
export HF_TOKEN="$(cat /mnt/c/GIT/llm-test-bench/HF_TOKEN.txt)"   # hf_ + 34 characters, as in the file
export HF_HUB_DISABLE_XET=1   # HF's Xet download backend froze this model's weights at 1.0 GB
export CUDA_HOME=/usr/local/cuda-13.0   # after `sudo apt install cuda-toolkit-13-0` (see Troubleshooting)
# ...or, until that toolkit is installed:
# export VLLM_USE_FLASHINFER_SAMPLER=0   # skip FlashInfer's JIT-compiled sampler
```
The first attempt hung with no error: the weight download stopped, and the server sat idle at 0%
GPU. If a download froze earlier, the new run should resume from the partial files; if it fails
instead, delete the model's `*.incomplete` files under `~/.cache/huggingface/hub/` and retry.
Without a matching CUDA 13.0 toolkit, FlashInfer logs `SM 12.x requires CUDA >= 12.9` and can't
JIT-compile its sampler at the end of startup (see Troubleshooting). `VLLM_USE_FLASHINFER_SAMPLER=0`
sidesteps that for this smoke test; the Qwen3.8 NVFP4 work (B7) will need the real toolkit.

```bash
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct-AWQ --max-model-len 8192 --gpu-memory-utilization 0.90 \
  --enable-auto-tool-choice --tool-call-parser hermes --port 8000
```
**Run it from outside `/mnt/c/GIT/vllm`** (e.g. `cd ~` first). Inside that checkout, vLLM's
`python -m` helper subprocesses import the checkout's own `vllm/` folder, which holds stale
May-built kernels, instead of the build copy, and fail with an ImportError about `_vllm_fa2_C`
(hit 2026-09-15). The harness isn't affected: it starts vLLM from `llm-test-bench`. A startup
warning about `VLLM_BIN` is harmless.

Don't pass `--quantization awq`: vLLM detects AWQ from the repo and picks its faster Marlin kernel
when it can. Checked 2026-09-15: the official repos exist (7B 5.6 GB, 14B 10.0 GB, 32B 19.3 GB).

**B3. Validation checklist** (from the helper's notes, adapted):
- [ ] Startup log shows no kernel errors and no attention-backend fallback (look for which
      backend it picked: FlashInfer or FlashAttention).
- [ ] `nvidia-smi` shows the expected VRAM use.
- [ ] `curl -s http://127.0.0.1:8000/v1/models` lists the model.
- [ ] A basic `POST /v1/chat/completions` works.
- [ ] **Tool calling round-trips**: send a request with a `tools` array and check that the reply
      has a structured `tool_calls` field, not tool JSON pasted into `content`. This silently breaks
      agentic harnesses even when everything else works. Parser: `hermes` for Qwen2.5-Coder;
      `qwen3_coder` or `qwen3_xml` for Qwen3.x models (both registered in this checkout; check the
      model card for which one).
- [ ] Prefix caching runs without error (`--enable-prefix-caching`). Chunked prefill is already on
      by default in this vLLM (`vllm/config/scheduler.py:116`).
- [ ] Record tok/s and time-to-first-token as the baseline.

**B3 result, Qwen2.5-Coder-7B-Instruct-AWQ, 2026-09-15:** everything passes except tool calling
with `tool_choice: "auto"`.
- Starts cleanly with `CUDA_HOME=/usr/local/cuda-13.0` (FlashAttention 2 for attention, FlashInfer
  sampler JIT-built). KV cache 6.4 GiB = 119,760 tokens at `--gpu-memory-utilization 0.90`.
- 300-token reply at 75.5 tok/s including prefill; streaming TTFT 50 ms, decode 80.7 tok/s.
- Tool call with `"auto"`: FAIL, deterministic. The model emits `<tools>{...}</tools>` instead of
  `<tool_call>{...}</tool_call>`, so the `hermes` parser leaves it in `content`. The chat template
  asks for `<tool_call>` correctly, so this is the 7B model. With `tool_choice: "required"` or a
  named function it PASSES, because vLLM constrains the output. Agentic clients that leave
  `tool_choice` on `"auto"` (most do) will break with this model; test the 14B AWQ next.

**B3 result, Qwen2.5-Coder-14B-Instruct-AWQ, 2026-09-15:** same pattern as the 7B.
- Starts with `--max-model-len 8192 --gpu-memory-utilization 0.92` (0.95 can't start, see
  Troubleshooting). KV cache 9,152 tokens (572 blocks of 16), per `/metrics` `cache_config_info`.
- 400-token reply at 42.7-43.8 tok/s including prefill; streaming TTFT 53 ms, decode 44.1 tok/s.
  GPU during generation: 13.7 GB used, 97% util, ~116 W.
- Tool call with `"auto"`: FAIL 2/2, identical `<tools>{...}</tools>` output. A system prompt telling
  it to use `<tool_call>` tags didn't help: it switched to `<json>{...}</json>`. `"required"` and a
  named function PASS. Conclusion: Qwen2.5-Coder (7B and 14B) is not usable for agentic clients
  that rely on `tool_choice: "auto"`, unless the client forces `"required"`.
- Test script: stdlib Python, checks `/v1/models`, chat speed (x2), tool calls (auto x2, required,
  named) and streaming TTFT at temperature 0.

**B3 result, cyankiwi/Qwen3.5-9B-AWQ-4bit (agentic pick), 2026-09-15:** everything passes. Steps and
the comparison table are in `vllm-plan.md`.
- Served with `--tool-call-parser qwen3_coder --reasoning-parser qwen3` at 0.92 and 32768. Weights
  7.55 GiB, KV cache 127,272 tokens (a Gated DeltaNet hybrid: only 8 of 32 layers keep KV) on that
  day's build. Re-measured 2026-09-17: the pool is 6.75 GiB = **209,615 tokens**, independent of
  `--max-num-seqs` (8 slots costs 0.5%), and 127,272 no longer reproduces at any setting. Re-read
  `GPU KV cache size` after any change, and compare only from an idle GPU — a server started before
  the previous one released its VRAM reports a smaller pool.
- 59-60 tok/s including prefill; streaming TTFT 40 ms, decode 60.3 tok/s. 13.2 GB, 94% util, ~110 W.
- Tool calls PASS with `"auto"` (2/2, and with thinking off), `"required"` and named. A round trip
  (tool result sent back) gives a correct final answer, and a question needing no tool gets no call.
- First start crashed with `FlashInfer requires GPUs with sm75 or higher`: `CUDA_HOME` wasn't set in
  that shell (`~/.bashrc` puts CUDA 12.8 first on PATH). See `vllm-plan.md` troubleshooting.
- 2026-09-16, real agentic check: the `llm-service-provider` selftest (Claude Code CLI through that
  repo's gateway on a test port, model served as `local-coder` at 65536) PASSES in 4 turns and 20 s.
  Claude Code accepts vLLM's thinking blocks; prefix caching cuts time to first token from 7.0 s to
  ~0.8 s on its ~17k-token requests. `bin/smoke.sh`'s `health` check fails only because vLLM's
  `/health` body is empty. Steps: `vllm-plan.md` Step 6.

**B4. Same models through the harness.**
```bash
export LLAMA_MODELS_DIR=~/models
VLLM_BIN=~/vllm-env/bin/vllm ./run.sh --backend vllm --model-file models/16gb.vllm \
  --models qwen2.5-coder:7b-awq qwen2.5-coder:14b-awq --tasks $TASKS
./run.sh --backend llama-server --model-file models/16gb.txt --models qwen2.5-coder:14b --tasks $TASKS
```
The last line is a same-box llama-server baseline for the 14B. On the 4090 rig, vLLM ran about 4×
slower than llama-server for single requests; check whether that holds on Blackwell.
Export `CUDA_HOME=/usr/local/cuda-13.0` first: the harness passes the environment on to `vllm serve`.

**B4 result, 2026-09-15:** `qwen2.5-coder:14b-awq` on `python_safe_div`: PASS, 33.5 tok/s, 12.7 s
(vLLM start 59 s). The results header labelled the vLLM version as `llama-server`; fixed 2026-09-16
in `lib/hw_snapshot.py`. Still open: the 7B, more tasks, the llama-server baseline, and the new
`qwen3.5:9b-awq` entry (the agentic pick, a thinking model served with `reasoning_parser=qwen3`).

**B5. GGUF plugin path.** Only after B2-B4 work.
```bash
mkdir -p ~/src && cp -r /mnt/c/GIT/vllm-gguf-plugin ~/src/
cd ~/src/vllm-gguf-plugin && uv pip install -e . --no-build-isolation
LLAMA_MODELS_DIR=~/models ./fetch-hf.sh models/16gb.txt --models qwen2.5-coder:14b
VLLM_BIN=~/vllm-env/bin/vllm ./run.sh --backend vllm --model-file models/16gb.vllm \
  --models qwen2.5-coder:14b-5060ti --tasks $TASKS
```
The plugin needs a CUDA toolkit whose `nvcc` matches PyTorch's CUDA 13.0: install
`cuda-toolkit-13-0` (apt; NVIDIA's repo is already configured on this box). `my-build.sh
--with-plugin` picks `/usr/local/cuda-13.0` automatically once it exists. The pip `nvidia/cu13`
folder in the venv is not a substitute: its `nvcc` is 13.4 but its headers are 13.0.

**B6. Concurrency, vLLM's real strength.** Manual: send 1, 2, 4 and 8 simultaneous requests to each
backend and compare total tok/s. Recent vLLM releases include `vllm bench serve` for this. For
multi-user serving, `--kv-cache-dtype fp8` frees VRAM for more context. Don't use it with
Qwen3.6-27B or Qwen3.8-27B: those drop `_EMPTY` in `python_hashmap` below f16 KV precision. Leave
speculative decoding off, both for determinism here and because it helps single-stream latency
rather than throughput.

**B7. After the second card arrives** (`./gpu-mode.sh multi`). The serving-side steps — switching
the lane to tp=2, capacity and DDR5 sizing, rollback — live in
`~/GIT/llm-service-provider/upgrade-dual-5060.md`; this section is the benchmark half:
1. Check the link each card got: `nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.width.current --format=csv`.
   With bifurcation, expect x8 each; tp=2 moves data between the cards on every token.
2. Re-run the B3 checklist at `--tensor-parallel-size 2`.
3. `vllm serve QUASAR-QAT/Qwen3.8-27B-QUASAR-NVFP4 --tensor-parallel-size 2 --max-model-len 32768 --enforce-eager`,
   then `qwen3.8-27b:nvfp4` from `models/2x16gb.vllm` through the harness. Watch `python_hashmap`.
4. Fallbacks: `qwen2.5-coder:32b-awq` (stock vLLM), then `qwen2.5-coder:32b-5060ti` (plugin).

   **Done 2026-09-23/24.** Links under load: card 0 gen5 x8, card 1 gen4 x4 (chipset slot); no
   GPU P2P, so NCCL all-reduces through host memory. `qwen3.8-27b:nvfp4` (eager, W4A16 on the
   old build): hashmap PASS, spot 9/10 at 30.0 tok/s. Tuned `qwen3.8-27b:nvfp4-next` (new build,
   W4A4, CUDA graphs): hashmap PASS, spot 10/10 at 32.6 tok/s. Serving-side A/B table:
   `upgrade-dual-5060.md` Step 6. Fallbacks (step 4) not needed.

**B8. Record** results in the `.vllm` files and in `CLAUDE.md`'s vLLM section, replacing its
"not yet vLLM-tested" notes. Done 2026-09-24, full B7 run: coding 19/19, web 4/4, L6 stepped 4/4,
context 8k-128k 5/5, multihop 5/5, node_paratrooper 1/7. Multi-agent serving results:
`upgrade-dual-5060.md` Step 7.

## Adjustments to the helper's notes

- **Qwen3-Coder-30B-A3B AWQ** (~16-17 GB) doesn't fit one 16 GB card; treat it as a 2×16 GB model.
  On the 4090 rig it ran 28.5 tok/s at tp=1 and failed `python_hashmap` (a base-model gap).
- **Devstral-Small-2505** is an old release; the current one is 2512 (`devstral-small-2`, 17/19
  coding on llama-server here).
- **Qwen3.6-27B AWQ**: untested here. A GPTQ build of it scored 18/19 and failed `python_hashmap`
  on vLLM; bartowski's GGUF on llama-server scored 19/19. Qwen3.8-27B (B7) is the newer target.
- **Qwen3.8-Flash-Next** is still not a vLLM job at this VRAM: `3116c5d06b` (2026-09-09) adds
  `--engram-config '{"cpu_offload": true}'` to keep its n-gram table in pinned host RAM, but the
  125B main model still needs far more than 32 GB. Keep using llama-server for it. On this box it
  still would not fit. (An earlier note here said vLLM turns pinned memory off under WSL outright;
  corrected 2026-09-16 — `vllm/platforms/cuda.py` makes it opt-in via `VLLM_WSL2_ENABLE_PIN_MEMORY=1`
  on WSL2 kernels >= 4.19.121, and this box runs 6.6.87.)

## Troubleshooting notes (first smoke test, 2026-09-15)

- **Run `vllm` from outside `/mnt/c/GIT/vllm`.** Inside it, the checkout's stale kernels shadow the
  build (ImportError about `_vllm_fa2_C`).
- **A silent hang while loading the model was a stalled Xet download.** Signs: partial files stuck at
  round sizes (1,024,000,000 bytes), the process asleep, the GPU at 0%, no error.
  `HF_HUB_DISABLE_XET=1` fixes it; the harness sets it by default for servers it starts.
- **Downloads ran at about 1.2 MB/s on 2026-09-15.** That was the network: the box was on an
  off-site Wi-Fi where everything, including a Cloudflare speed test, was equally slow. On the home
  network, `fetch-hf.sh` had pulled the 111 GB Flash-Next GGUF at roughly 60 MB/s. For big models,
  pre-download so you can watch progress: `HF_HUB_DISABLE_XET=1 ~/vllm-env/bin/hf download <repo>`.
  (The "Reconstructing" progress bar it shows is just `huggingface_hub`'s label for bytes written to
  disk; it doesn't mean Xet is in use.)
- **A restarted download doesn't resume the old partial file;** it starts a new `*.incomplete`.
  Aborted runs leave dead partials in `~/.cache/huggingface/hub/models--<org>--<name>/blobs/`;
  delete them once the model has fully downloaded.
- **The token must be `hf_` plus 34 characters.** An exported token missing its `h` produced
  "You are sending unauthenticated requests to the HF Hub". Export it straight from the file (B2), or
  run `~/vllm-env/bin/hf auth login` once to save it to `~/.cache/huggingface/token`.
- **Don't trust `/proc/<pid>/environ` for vLLM processes.** vLLM renames them with `setproctitle`,
  which overwrites the start of that memory, so variables look missing when they aren't.
- **Expected, harmless warnings:** "Pinned memory is not available on this platform" (vLLM leaves it
  off under WSL unless `VLLM_WSL2_ENABLE_PIN_MEMORY=1`) and "Unknown vLLM environment variable
  detected: VLLM_BIN" (the harness's own variable).
- **`FileNotFoundError: ... 'ninja'` happens AFTER the useful log lines.** Worth knowing when
  scripting: the engine prints `GPU KV cache size` and the memory profile *before* FlashInfer's JIT
  warmup, so a script that only scrapes those numbers succeeds while every server it started is
  actually dying seconds later (hit 2026-09-17 — it also left VRAM in flux, which silently skewed a
  back-to-back KV comparison). Any script that starts `vllm serve` by hand must put
  `~/vllm-env/bin` on PATH, not just set `CUDA_HOME`.
- **`FileNotFoundError: ... 'ninja'` at the very end of startup** (after CUDA graph capture): during
  warmup, FlashInfer compiles its top-k/top-p sampling kernel and calls `ninja`. It's installed in
  `~/vllm-env/bin`, which is only on PATH once the venv is activated, so run
  `source ~/vllm-env/bin/activate` first. The harness adds that folder to PATH itself. If the build
  itself fails, `VLLM_USE_FLASHINFER_SAMPLER=0` switches to PyTorch's sampler instead.
- **`CUDA compiler and CUDA toolkit headers are incompatible`** during that same FlashInfer build:
  FlashInfer's bundled CCCL requires `nvcc`'s major.minor to equal the CUDA headers' version. With
  `CUDA_HOME` on the pip `nvidia/cu13` folder, `nvcc` is 13.4 but the headers are 13.0
  (`CUDART_VERSION 13000`), so it fails. The system toolkit (12.8) is below FlashInfer's 12.9
  minimum for SM 12.x. Fix: `sudo apt install cuda-toolkit-13-0` and `CUDA_HOME=/usr/local/cuda-13.0`
  (verified 2026-09-15: FlashInfer's sampler then builds for sm_120f in ~40 s and is cached). Make
  sure no earlier `export CUDA_HOME=.../nvidia/cu13` is still set in the shell; it overrides this.
  13.0 matches PyTorch's CUDA and stays within the driver's CUDA 13.1; a 13.4 toolkit would be newer
  than the driver. Side effect: `/usr/local/cuda` is managed by `update-alternatives` in auto mode
  (currently 12.8, priority 128), so installing 13.0 will likely repoint it to 13.0;
  `sudo update-alternatives --set cuda /usr/local/cuda-12.8` puts it back. `llamacpp/build-llama.sh`
  picks the newest `/usr/local/cuda-X.Y` regardless, so the next llama.cpp rebuild would use 13.0.
- **`curl http://127.0.0.1:8000/...` hangs although the server is up.** This box uses WSL2
  `networkingMode=mirrored`, where Windows' firewall drops loopback traffic to ports bound on
  `0.0.0.0` (vLLM's default). Use the machine's address instead: `curl http://$(hostname -I | awk
  '{print $1}'):8000/v1/models` (`10.255.255.254` worked on 2026-09-15), or start vLLM with
  `--host 127.0.0.1`, as the harness does for llama-server (untested for vLLM). The harness's vLLM
  client already falls back to the LAN address on its own (`_detect_connect_url()`).
- **`ValueError: To serve at least one request with the model's max seq len ...`** at startup: the KV
  cache doesn't fit. On a 16 GB card vLLM needs ~2.4 GB (7B) to ~3.5 GB (14B) besides the weights.
  The 14B AWQ at `--max-model-len 16384` had only 1.36 GiB of KV at 0.90 (it needed 3.0 GiB).
  `--max-model-len 8192 --gpu-memory-utilization 0.92` fits (~1.68 GiB of KV, ~9k tokens).
- **`ValueError: Free memory on device cuda:0 (14.8/15.93 GiB) on startup is less than desired GPU
  memory utilization (0.95, 15.13 GiB)`**: Windows (display, desktop apps) holds ~1.1 GiB of the card.
  `nvidia-smi` inside WSL does not show it (it reported 0 MiB used), so 0.95 looks safe but isn't.
  The real ceiling is free/total = 0.929; use 0.92. Check it with
  `~/vllm-env/bin/python -c "import torch; print(torch.cuda.mem_get_info())"`. Closing GPU-heavy
  Windows apps (browser, games) raises it a little.

- **A benchmark run competes with the service provider.** Since 2026-09-16 that repo's units are
  enabled on this box, so a lane holds most of the card from boot and a `./run.sh` here fails to
  allocate. Which lane depends on the active backend: `vllm-local-coder` (~15 GB), or `llm-backend`
  running `qwen3.8-flash-next` (~10.5 GB of VRAM **and ~75 GB of page cache**, which a benchmark
  needs just as badly). Run `~/GIT/llm-service-provider/bin/llmctl stop` first (frees the GPU,
  leaves the gateway up), and `bin/llmctl start` afterwards.

## Order

A1-A3 first: quick and independent of vLLM. Then B1-B3 to learn whether vLLM works on this card,
then A4, B4-B6. B7 waits for the second card.
