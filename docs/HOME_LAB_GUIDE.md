# Home Lab LLM Guide: llama.cpp + vLLM on Consumer Multi-GPU Hardware

Practical guidance distilled from empirical benchmark runs on RTX 4090 + RTX 3090 (PCIe, no NVLink).
Numbers marked with `*` are confirmed on this hardware; numbers marked `est.` are estimates extrapolated
from confirmed results or architecture math. Sections marked **[NOT YET VALIDATED]** describe features
referenced in upstream documentation that have not been tested in this bench; they are included as
starting points to fill in once vLLM runs complete.

---

### 1. llama.cpp vs vLLM — Two Complementary Engines

These are not competitors. They optimize for different workloads.

| | llama.cpp (`llama-server`) | vLLM (`vllm serve`) |
|---|---|---|
| **Primary strength** | Single-user, interactive, frequent model swaps | Concurrent requests, always-on serving |
| **Model format** | GGUF (broad ecosystem, aggressive low-bit quants) | HF safetensors or GGUF (dense models only) |
| **MoE support** | Excellent — all A3B/A22B MoE GGUFs work | GGUF MoE works with patched `--quantization gguf` flag (confirmed 31.2 tok/s tp=1); stock vLLM still fails with `mlp.experts.*` error; use AWQ/FP8 HF format with stock vLLM |
| **Startup time** | Fast — model swaps in seconds | Slow — CUDA graph capture ~400s for 32B; `enforce_eager` saves ~1 GB VRAM at ~20% speed cost |
| **KV cache** | `q8_0` or `f16` per model flag | FP8 (`kv_cache_dtype=fp8`) halves memory; FP16 default |
| **Prefix caching** | Not available | Built-in; significant TTFT wins on repeated system prompts |
| **Mixed GPUs** | Tolerant — tensor_split handles mismatched VRAM well | Problematic — TP runs at the slower card's bandwidth; all ranks must complete each step |
| **Context length** | Limited by KV budget; `max_ctx` set per model | `max_model_len` set at server startup; FP8 KV doubles effective range |

**Decision rule:**
- Single user, interactive coding, or you swap models frequently → **llama.cpp**
- Concurrent agents, always-on API server, one stable model → **vLLM**
- Evaluating a new model quickly → **llama.cpp** (no CUDA graph capture wait)
- Production serving with prefix-heavy workloads (RAG, few-shot) → **vLLM**

---

### 2. VRAM Tier Recommendations

#### 2.1 Single 24 GB GPU (RTX 4090 or RTX 3090)

The practical ceiling without tensor parallelism. KV headroom is tight for large dense models;
MoE models punch well above their weight here (only A3B ≈ 3B active weights generate at once).

**Recommended models (llama-server, confirmed):**

| Role | Model | VRAM | tok/s\* | Score | Notes |
|---|---|---|---|---|---|
| Daily coding | `noctrex-qwen3.6:35b` | ~13 GB | \*118 | 32/33 | Best single-GPU all-rounder; Ampere+ required |
| Coding-perfect | `equinox:31b` | ~16.4 GB | \*35.5 | 19/19 coding + 4/4 web | Only single-GPU model with both; dense; context ceiling 32k |
| Fast/interactive | `glm4.7-flash` | ~16 GB | \*111 | 29/33 | Skill L4; passes stepped L5+L6; fails python_hashmap/dijkstra |
| Reasoning | `deepseek-r1:32b` | ~20 GB | \*31 | 18/19 | Q4_K_M; good coding, not hashmap; context limited to 32k on single GPU |
| Context-capable | `qwen3-30b:2507` | ~17 GB | \*163 | 32/37 | 64k context at 9.2 tok/s; 128k OOM; multihop 3/3 |

**Context ceiling on single 24 GB:**
Dense 32B models (equinox:31b, qwen2.5-coder:32b-q4) are limited to `max_ctx=32768`.
At 64k: f16 KV (~11 GB) + 16 GB weights exceeds 24 GB. For 64k+ context, use 2×24 GB.

MoE models (qwen3-30b:2507, glm4.7-flash) can reach 64k but at dramatically reduced speed
(9.2 tok/s vs 163 tok/s for qwen3-30b:2507) as KV spills beyond available VRAM.

#### 2.2 Dual 24 GB (2× RTX 4090 / 4090+3090 — 48 GB total)

Tensor parallel removes the KV ceiling for most 32B models. MoE models continue to run
optimally on a single GPU; tensor_split for MoE is mainly useful for context tasks.

**Confirmed RTX 4090 + RTX 3090 (PCIe, no NVLink):**

| Role | Model | VRAM | tok/s\* | Score | Context |
|---|---|---|---|---|---|
| Best all-round | `qwen3.6:27b` | ~17 GB | \*40.2 | 32/33 Skill L5 | 256k at 26 tok/s |
| Best MoE quality | `noctrex-qwen3.6:35b` | ~13 GB | \*121 | 32/33 Skill L5 | 256k at 75 tok/s |
| Best coding | `qwen2.5-coder:32b-q4` | ~18.5 GB | \*36.5 | 19/19 PERFECT | 32k (server caps despite 48 GB) |
| Best reasoning | `deepseek-r1:32b` | ~26 GB | \*34 | 18/19 | 64k PASS (19.7 tok/s); 128k NO\_BLOCKS |
| Fast MoE | `qwen3.5:35b` | ~9 GB active | \*153 | 26/33 | 128k at 107 tok/s; 256k at 85.6 tok/s |

**Note on PCIe vs NVLink:** Dense tensor-parallel is bandwidth-bound. RTX 4090 + RTX 3090
(PCIe) caps dense 32B at ~37 tok/s and dense 70B at ~20 tok/s. NVLink would roughly
double those figures for dense models. MoE models are not bandwidth-bound between GPUs
and are unaffected.

**Note on silent context cap:** `qwen2.5-coder:32b-q4` and `qwen2.5-coder:14b` silently
cap at `max_ctx=32768` even when started at `ctx=65536` on 48 GB. KV math predicts
they should fit; llama-server internally limits them anyway. Root cause unknown (likely
flash_attn workspace allocation). Use `max_ctx=32768` in their model files to get
`SKIPPED_CTX` instead of `CTX_TRUNCATED`.

#### 2.3 Triple 24 GB (3× GPU — 72 GB total)

> **All speeds estimated** — no confirmed benchmark runs on this tier yet.

What 72 GB unlocks vs 48 GB:
- `gpt-oss:120b` fully GPU-resident (removes `n_cpu_moe` CPU offload; was ~17 tok/s RAM-bound; est. ~80–100 tok/s)
- `llama4-scout:17b` (109B MoE total) GPU-resident (was 3.3 tok/s RAM-bound; est. ~60 tok/s)
- Dense 32B `max_ctx=131072` feasible (per-GPU weight share drops to ~6 GB, leaving ~18 GB KV)
- Dense 70B (`llama3.3:70b-q4`) estimated ~22–25 tok/s (modest improvement; still PCIe-bound)

**Recommended daily driver:** `noctrex-qwen3.6:35b` (unchanged from 48 GB — MoE doesn't
gain from the 3rd GPU on coding tasks; keeps single-GPU VRAM footprint).

See `models/3x24gb.txt` for configured models.

#### 2.4 96 GB and Beyond

Diminishing returns on PCIe. 4-way PCIe dense 70B adds minimal tok/s vs 3-way.
Main unlock: `qwen3-next:80b` context_256k (architecture still TBD — may cap at 131k).
No new model class unlocks at 96 GB that 72 GB doesn't handle. Not a priority upgrade.

---

### 3. Recommended vLLM Runtime Defaults

> **[PARTIALLY VALIDATED]** — baseline params confirmed on AWQ (tp=1/tp=2) and GGUF (tp=1)
> for Qwen3-Coder-30B-A3B (confirmed 2026-07-05/06). FP8 KV and tp=2 performance not confirmed
> on this hardware (FP8 arm dead on RTX 3090 Ampere). Update remaining `est.` values once
> additional runs complete.

```bash
# Baseline profile for tp=2 coding workloads on 2× 24 GB
vllm serve <model-id> \
  --tensor-parallel-size 2 \        # TP across GPUs; TP size must divide num_attention_heads
  --dtype auto \                     # let vLLM pick bf16/fp16
  --kv-cache-dtype fp8 \             # halves KV memory; verify python_hashmap passes (precision canary)
  --gpu-memory-utilization 0.88 \    # 0.88 confirmed safe with display adapter; 0.94 exceeded free VRAM
  --enable-prefix-caching \          # faster TTFT on repeated system prompts; no quality impact
  --max-model-len 32768              # per model; see tier notes below
```

**Tensor parallel constraint:** TP size must evenly divide the model's `num_attention_heads`.
For example, a 32-head model supports TP=1, 2, 4, 8 — not TP=3. Check `config.json` before
setting an unusual TP value.

**Mismatched GPU warning:** vLLM's TP runs synchronously — each forward pass waits for all
ranks to complete. On RTX 4090 + RTX 3090 (PCIe, no NVLink), the 3090's slower memory
bandwidth (~936 GB/s vs 4090's ~1008 GB/s) becomes the bottleneck. llama.cpp tensor_split
tolerates the mismatch far better because it pipelines layer transfers asynchronously.

**`max_model_len` by tier:**

| Tier | Dense 32B | Dense 32B (FP8 KV) | MoE 30B | Dense 70B |
|---|---|---|---|---|
| Single 24 GB | 8 192 | 16 384 est. | 8 192 (GGUF patched vLLM; KV ceiling ~13 760) | does not fit |
| 2× 24 GB | 32 768–65 536 | 65 536–131 072 | 32 768 (AWQ HF; or GGUF patched) | 32 768 |

---

### 4. Recommended llama.cpp Runtime Defaults

These flags are confirmed on RTX 4090 + RTX 3090 across all models in `models/24gb.txt`
and `models/2x24gb.txt`.

```bash
# Baseline model file entry (single GPU)
model-name  model.gguf  ngl=999,no_mmap,flash_attn,batch_size=512,ubatch_size=128

# Dual GPU (tensor_split)
model-name  model.gguf  ngl=999,no_mmap,tensor_split=1|1,flash_attn,batch_size=512,ubatch_size=128
```

| Flag | Effect | Notes |
|---|---|---|
| `ngl=999` | All layers to GPU | Use exact layer count only if VRAM is borderline |
| `no_mmap` | Disable memory-mapped file I/O | Faster model load from NVMe; avoids swap on tight VRAM |
| `flash_attn` | FlashAttention kernel | Required for Ampere+; significant speed improvement; mandatory for MoE |
| `tensor_split=1\|1` | Equal layer split across 2 GPUs | `1\|1` = 50/50; adjust for unequal VRAM (e.g. `1.5\|1` for 4090+3090 with tight fit) |
| `cache_type_k/v` | KV cache quantization | Default `q8_0`; use `f16` for precision-sensitive models (see §5) |
| `batch_size=512` | Prompt-eval batch size | Default; larger batch → faster prompt eval |
| `ubatch_size=128` | Micro-batch for generation | Default for balanced throughput |
| `max_ctx=N` | Context length cap | Set to match what the model's VRAM allows; prevents server from over-allocating |

**MoE-specific:** MoE models with MTP heads (noctrex `MTP_MXFP4_MOE`) — disable spec
decoding (`--spec-type draft-mtp` absent). Spec decoding breaks `temperature=0` determinism.

**Thinking models:** Set `thinking` flag in the model file. The harness prepends the
`"After your reasoning"` system prefix. Do not set `thinking` on semi-thinking models
(gpt-oss:20b, gemma4:26b) — they generate verbose reasoning in plain text and don't need it.

---

### 5. KV Cache Precision Guidance

#### For llama.cpp

The default is `q8_0` for both K and V cache. This is the right choice for almost all models.

**Exception — the python_hashmap precision canary:**

The `python_hashmap` task (L5 tombstone algorithm) is acutely sensitive to KV precision on
specific architectures. With `q8_0` KV, some models omit `_EMPTY = None` from module-level
definitions while correctly implementing everything else — a single wrong token at a precision
boundary.

| Model | KV needed | Reason |
|---|---|---|
| `qwen3.6:27b` | `f16` **required** | Fails python_hashmap with q8_0; passes cleanly with f16 |
| `qwen3.5:27b` | `q8_0` fine | Same param count, different architecture; passes hashmap with q8_0 |
| `qwen2.5-coder:32b-q4` | `q8_0` fine | Dense 32B; passes cleanly |
| MoE models (A3B) | `f16` used by default | Conservative choice; no confirmed regression with q8_0 |
| `equinox:31b` (dense 31B) | `f16` used | Unknown architecture; f16 is the safe default |

Rule: use `f16` KV for `qwen3.6:27b` specifically. Do not apply to other 27B models —
precision sensitivity is architecture-specific, not size-specific.

#### For vLLM

> **[NOT YET VALIDATED on this hardware]** — recommended based on vLLM documentation and
> confirmed llama.cpp results. Will update once vLLM benchmark runs complete.

Default to `kv_cache_dtype=fp8`. This halves KV memory and enables significantly longer
context lengths. Before committing `fp8` KV for a model, verify `python_hashmap` passes
(run `bench.py --tasks python_hashmap` against the vLLM backend). If it fails, revert to
`kv_cache_dtype=auto` (effectively fp16).

The GPTQ INT4 (C4-calibrated) result is a warning: `AxisQuant/Qwen3.6-27b-gptq-int4` failed
`python_hashmap` with the same `_EMPTY` omission as `q8_0` KV — C4-calibrated GPTQ also
loses precision on this task. AWQ is preferred over GPTQ for coding benchmarks.

---

### 6. CPU KV Offloading

> **[NOT YET VALIDATED on this hardware]** — described in vLLM documentation; not yet
> tested in this bench. Included as a reference starting point.

CPU KV offloading pages KV cache blocks to system RAM when GPU KV budget is exhausted.
It is not a default and should not be enabled speculatively.

**When it makes sense:**
- You need one more concurrent request than VRAM KV headroom allows
- Or you need a slightly longer context window without adding a GPU

**When it doesn't make sense:**
- As a substitute for sufficient VRAM — continuous paging degrades throughput sharply
- When PCIe bandwidth is already the bottleneck (e.g. 2× RTX 3090 tensor-parallel — adding
  CPU↔GPU KV paging on top of inter-GPU tensor transfers is likely to collapse throughput)

**Example (from vLLM docs, not confirmed here):**
```bash
vllm serve <model> --kv-offloading-backend native --kv-offloading-size 8
```

The mental model: good for "I need 8 GB more KV for one request"; bad for "I want to run
a 70B model on 24 GB". Expect noticeable latency increase for requests that trigger paging.

---

### 7. Prefix Caching

Enable by default in vLLM. Add `--enable-prefix-caching` to the serve command (or
`enable_prefix_caching` in the model file params field).

**When it helps most:**
- Repeated system prompts (every request starts with the same 2k-token system context)
- Few-shot templates shared across many requests
- Agentic workflows where tool definitions or context accumulate across turns

**What it does:** Caches the KV state for token sequences seen before, so the prefill
computation is skipped on cache hit. Primarily reduces time-to-first-token (TTFT); has
no meaningful effect on decode (generation) speed.

**What it doesn't do:** It does not reduce decode latency. It does not help single-request
benchmarks where every prompt is unique (like this bench's coding tasks). The benefit
scales with cache hit rate — in a diverse open-ended workload, hits may be rare.

**For this bench:** Not relevant for the benchmark harness (every task has a unique prompt).
Enable it for interactive serving and agent workloads.

---

### 8. Model Sleep / Wake Modes

> **[NOT YET VALIDATED on this hardware]** — described in vLLM documentation; not yet
> tested in this bench. Numbers below are from vLLM docs, not measured here.

vLLM supports two sleep levels to free VRAM between requests without a full cold restart:

| Mode | What is freed | Wake time (docs) | CUDA graphs |
|---|---|---|---|
| L1 (weights to CPU) | GPU weights only | ~2–3s | Preserved |
| L2 (weights discarded) | GPU weights + KV | ~7–8s | Preserved |

Both levels preserve CUDA graph capture state, so wake does not trigger the full ~400s
cold start required for a fresh `vllm serve` launch.

**When it's useful:**
- Benchmarking many models sequentially (load → test → sleep → load next)
- Intermittent workloads where the server is idle for long stretches

**When it's not needed:**
- A stable always-on server running one model continuously
- llama.cpp (model swaps are already fast; no equivalent concept needed)

---

### 9. Concurrency Benchmark

> **[NOT YET VALIDATED]** — this experiment type is not yet implemented in this bench
> harness (`bench.py` currently sends one request at a time). A harness change is required
> to send concurrent requests. See `next-runs.md` run #12.

vLLM's primary architectural advantage over llama.cpp is continuous batching: multiple
requests share the forward pass, so aggregate throughput scales super-linearly with
concurrent users up to the GPU's compute ceiling.

**Proposed benchmark protocol:**

Send N concurrent coding requests (same task, different model responses) and measure:

| Metric | Definition |
|---|---|
| Aggregate tok/s | Total tokens generated across all requests / wall time |
| Wall time | Time from first request sent to last response received |
| TTFT | Time from request sent to first token returned (P50 / P95) |
| Per-request latency | Total time per request (P50 / P95) |

**N values to test:** 1, 2, 4, 8.

N=1 is a baseline sanity check (should approximately match single-request llama.cpp speeds).
N=8 is where vLLM's batching advantage becomes significant; llama.cpp serializes all 8
requests, so its N=8 wall time is 8× its N=1 wall time.

---

### 10. Model Selection Cheatsheet

Confirmed scores from `models/24gb.txt` (single RTX 4090) and `models/2x24gb.txt` (48 GB).

| Use case | Recommended model | Backend | tok/s\* | Notes |
|---|---|---|---|---|
| Daily coding, single GPU | `noctrex-qwen3.6:35b` | llama-server | \*118 | 32/33, Skill L5, Ampere+ |
| Coding-perfect, single GPU | `equinox:31b` | llama-server | \*35.5 | 19/19 + 4/4 web; context 32k only |
| Fast interactive, single GPU | `glm4.7-flash` | llama-server | \*111 | 29/33 Skill L4; passes L5+L6 stepped |
| Reasoning + long context | `deepseek-r1:32b` | llama-server | \*34 | 2×24 GB; 64k context; hashmap fails |
| Reasoning, best quality | `qwen3.5:35b` | llama-server | \*153 | 2×24 GB; thinking; 128k at 107 tok/s |
| Coding-perfect, 48 GB | `qwen2.5-coder:32b-q4` | llama-server | \*36.5 | 19/19 PERFECT; context silently capped 32k |
| Best 48 GB all-round | `qwen3.6:27b` | llama-server | \*40.2 | 32/33 Skill L5; 256k at 26 tok/s |
| Speed + quality, 48 GB | `noctrex-qwen3.6:35b` | llama-server | \*121 | 32/33; 256k at 75 tok/s |
| Large review (3×24 GB) | `gpt-oss:120b` | llama-server | ~90 est. | GPU-resident at 72 GB; was 17 tok/s RAM-bound |
| vLLM AWQ, single GPU | `cpatonn/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit` | vLLM tp=1 | \*28.5 | 18/19; python_hashmap FAIL (base gap); 4× slower than llama-server |
| vLLM GGUF (patched), single GPU | Q4_K_M via `--quantization gguf` (patched vLLM) | vLLM tp=1 | \*31.2 | 15/16 eligible; ctx≤8192 on single 24 GB; ~10% faster than AWQ |

**Rejected models (do not add to regular sets):**

| Model | Reason |
|---|---|
| `phi4-reasoning-plus:14b` | Loops in reasoning planning phase; never emits `BEGIN_FILE`; 0/13 |
| `lfm2:8b` | 320 tok/s speed record but fails L2+ tasks; `node_para_core` NO\_BLOCKS |
| `north-mini-code` | Agentic preamble exhausts budget before code; 0.130 p/k (worst efficiency seen) |
| Dense 70B on PCIe 48 GB | `llama3.3:70b` 6/10 at 17.4 tok/s; MoE 80B at 109 tok/s is strictly better |

---

### 11. What to Ignore for Home Labs

**Disaggregated prefill/decode:** Separates prefill compute (CPU-like, compute-bound)
from decode (memory-bound generation) across different machines or GPU pools. Only relevant
at datacenter scale with heterogeneous GPU fleets. Adds routing and network complexity that
provides no benefit in a single-node setup.

**500-concurrency benchmarks:** Vendor throughput claims at N=500 concurrent users reflect
a queuing regime that home labs never reach. The meaningful concurrency range for a home
lab or small team is N=1 to N=8. Aggregate tok/s at N=500 tells you nothing about
interactive latency at N=2.

**FP8 weight quantization experiments:** The MoE Q4→Q6 experiment on `qwen3.5:35b`
confirmed no quality change with 36% slower speed and a requirement for dual GPU. For MoE
models on this hardware, Q4_K_M is the correct format. Do not repeat for other MoE models.

**MXFP4 vs Q4_K_M for A3B MoE:** For Qwen3-30B-A3B architecture, Q4_K_M is ~7% faster
than MXFP4 (185 vs 172 tok/s) with no quality difference. MXFP4 saves ~1 GB VRAM. Not
worth the speed penalty unless VRAM is the binding constraint.

---

*Last updated: 2026-07-04. Confirmed results: llama-server runs through equinox:31b 37-task
(2026-07-04). vLLM results: pending first benchmark runs (#9–12 in `next-runs.md`).*
