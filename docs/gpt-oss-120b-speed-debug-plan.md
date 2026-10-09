# gpt-oss:120b on 3×24 GB: speed and hang debugging plan

Status: **plan, nothing run yet** (written 2026-10-09 23:10). Config under test: `models/3x24gb.txt`
`gpt-oss:120b` — `ngl=999, tensor_split=1|1|1, q8_0 KV, flash_attn, -b 512 -ub 128`, pinned llama.cpp
`67a17c17c` (pinned for qwen3.8-flash-next; built with `GGML_CUDA_GRAPHS=ON`), server started as
`llama-server --ctx-size 24576 --threads 10 --tensor-split 1,1,1 --flash-attn on ...`.

## What we know

**1. Decode speed falls with the length of the answer, not of the prompt.** From every stored
gpt-oss:120b result on this rig (`output/*.json`):

| prompt tokens | generated tokens | tok/s | task |
|---|---|---|---|
| 465–1,600 | 150–860 | 43–75 | short coding tasks |
| 1,481–1,724 | 1,167–1,834 | 20–26 | tokenizer, lfu_cache, para_core |
| 3,195–8,726 | 1,862–7,166 | 8.8–12.6 | para_turret/entities/combat, csv_nordic, gamedev |
| 24,391 / 48,526 | 167 / 100 | 58.0 / 53.4 | context_32k / context_64k |

A 48k-token prompt still decodes at 53 tok/s, so context depth is not the cause. Note that the harness's
tok/s is llama-server's `predicted_per_second`, an average over the whole answer: if per-token latency
grows as the answer grows, a long answer's average collapses even though its first tokens were fast.

**2. The busy thread is waiting on a cross-GPU copy.** `perf record -g` (20 s, then DWARF unwinding,
2026-10-09 ~23:05, on the live server): 86% of the main thread's samples are in `cudaStreamSynchronize`,
called from `ggml_backend_cuda_buffer_set_tensor` inside `ggml_backend_sched_graph_compute_async`, i.e.
the scheduler copying a split's input from one backend to the next. The thread was 100% user-space
(spin-waiting), with almost no system time. Profiles: scratchpad `perf-gptoss.data`,
`perf-gptoss-dwarf.data` (not kept in the repo).

**3. It also hangs.** The same profile was taken during a hang. hwmonitor (`output/hwmonitor-20261009-210117.log`,
10-minute buckets):

| time | GPUs |
|---|---|
| 21:00–22:10 | working: up to 100% utilization, 120–220 W |
| 22:10–22:40 | idle, ~20 W: `cs_mesh_winding` hung, TOOL_ERROR at 2,400 s, 0 tokens |
| 22:40–22:50 | working (`cs_light_port` starts) |
| 22:50–(23:26) | idle again, near-zero PCIe traffic (`nvidia-smi dmon`), server spin-waiting |

The finished run (01:30) hung 3 times in 44 requests: `cs_mesh_winding`, `cs_light_port`,
`cs_predict_reconcile` — all long gamedev answers; none of the 17 short diag answers hung.
Earlier gpt-oss:120b runs here hit one TOOL_ERROR in about 70 tasks (context_16k, 2026-08-11); this
run hit two in 13. During this run the Unity builder was running a CarrierDominion Win64 build and a
headless Chromium on the same machine.

## Hypotheses

| | Hypothesis | Explains | Test |
|---|---|---|---|
| H1 | Per-token synchronous cross-GPU copies (no peer access under WSL2 → staged through the host) whose cost grows with something tied to answer length | slowdown | speed curve (P2) with and without the split; master build |
| H2 | A cross-GPU copy or event that never completes (deadlock on the WSL2 GPU paravirtualization path) | hangs | thread dump of a hung server (P1) |
| H3 | Flash-attention kernel path (attention sinks / SWA) on Ampere + Ada mix | hangs, maybe speed | `flash_attn` off (P3) |
| H4 | CUDA graphs (build has `GGML_CUDA_GRAPHS=ON` since 2026-09-04) | hangs, maybe speed | `GGML_CUDA_DISABLE_GRAPHS=1` (P3) |
| H5 | GPU contention from other work through the shared WSL2 GPU driver (the Unity builder) | hangs | P3 with the builder idle vs active |
| H6 | A llama.cpp bug fixed since `67a17c17c` | both | master worktree `~/GIT/llama.cpp-master` (P3) |
| H7 | q8_0 KV dequantisation cost in the flash-attention path at growing KV | slowdown | f16 KV (P3) |

Advice from other sources that does not fit this setup: lower `-b`/`-ub` (already 512/128), contexts
past ~40k (24,576 here, hangs at 6–15k tokens), NUMA (single socket).

## Plan

### P0 — preconditions (every phase)
- Nothing else running: `BENCH_ABORT_ON_BUSY=1 python3 lib/load_check.py` passes, the Unity builder is
  idle (except in the H5 arm), `~/GIT/llm-service-provider/status.sh` shows no active backend.
- `./gpu-mode.sh multi`, power limits 260/240/240 W, hwmonitor on (`./run.sh`, never bare `bench.py`).
- Record for each arm: binary commit, flags, env, start/end time, hwmonitor log name.

### P1 — capture a hang (≈ whenever one happens; no extra GPU time)
1. `sudo sysctl kernel.yama.ptrace_scope=0` (the user runs this; back to 1 afterwards).
2. When GPUs go idle with the server thread at 100%: `gdb -p <pid> -batch -ex "thread apply all bt" > hang-bt.txt`
   (stops the process for a second; it is hung anyway).
3. Also `perf record -g -t <tid> -- sleep 10` and `nvidia-smi dmon -s ut -c 10`.
4. Read: which split/backend pair the copy is between (GPU0↔1, 1↔2, GPU↔CPU), and what the other threads
   (`cuda-EvtHandlr`) are doing. A GPU↔GPU copy points at H2/H5; a flash-attention kernel in flight at H3.

### P2 — measure the speed curve (≈ 30 min)
Fixed prompt (the `cs_coord_bam` prompt, ~6k tokens, via `bench.py --export-task` → `PROMPT.txt`), sent
straight to a running llama-server with `n_predict` = 250, 500, 1000, 2000, 4000 (non-streaming,
`temperature 0`, `ignore_eos`). From each response's `timings`, marginal cost per token =
Δ`predicted_ms` / Δ`predicted_n` between steps.
- Flat marginal cost → the slowdown is something else (e.g. reasoning tokens counted differently).
- Rising marginal cost → H1/H7; repeat with `llama-bench -m <gguf> -p 6000 -n 4000 -ts 1/1/1 -fa 1 -ctk q8_0 -ctv q8_0`
  (no server): if llama-bench stays fast, the cost is in the server loop, otherwise in the compute graph.

### P3 — configuration A/B (≈ 3–4 h)
Arms, each one change against the baseline:

| arm | change | hypothesis |
|---|---|---|
| A | baseline (as today) | — |
| B | `flash_attn` removed | H3 |
| C | env `GGML_CUDA_DISABLE_GRAPHS=1` | H4 |
| D | `LLAMA_SERVER_BIN=~/GIT/llama.cpp-master/build/bin/llama-server` | H6 |
| E | `cache_type_k=f16,cache_type_v=f16` | H7 |
| F | baseline with the Unity builder deliberately active | H5 |

Per arm: the P2 speed curve (n_predict 500 and 4000 only), then `cs_mesh_winding` (the task that hung)
4× through `./run.sh --tasks cs_mesh_winding --model-timeout 900` so a hang costs 15 minutes. Tonight's
rate was ~1 hang per 6 tasks, so four repeats can show a difference but not prove a fix: any arm with zero
hangs gets 8 more repeats before it counts.

### P4 — only if P1–P3 point at the GPU side
Install Nsight Systems (`nsight-systems-cli`, NVIDIA apt repo) and record one long generation:
`nsys profile -t cuda,nvtx --capture-range=cudaProfilerApi ...` to see copy/kernel timing per token.
This also serves the open qwen3.8-flash-next speed question (CLAUDE.md finding 9).

## Decision rules
- An arm that removes hangs (0 in 12) and does not lose capability (the gamedev/coding tasks it passes
  stay passing) becomes the `models/3x24gb.txt` config for gpt-oss:120b; record why next to it.
- An arm that raises long-answer speed by more than 1.5× at n_predict 4000 is adopted the same way.
- If only the master build (D) helps, run it for gpt-oss:120b via its own `LLAMA_SERVER_BIN` and keep
  the pin for qwen3.8-flash-next.
- Whatever the outcome: re-run the tasks that hit TOOL_ERROR tonight on the chosen config.

## Harness gaps noticed
- A hung request is only detected by the client timeout (2,400 s here). A watchdog that aborts a request
  when the GPUs have been idle for N minutes while the request is open would turn a 40-minute hang into
  a few minutes. Not built.
- llama-server's stderr is piped and discarded unless the harness runs in debug mode, so the server's own
  log (graph splits, warnings) is lost for normal runs.
