# Local LLM Model Status — May 2026

All results measured on RTX 3090 24 GB, AMD Ryzen 7 9800X3D, 86 GB RAM,
llama-server 9237 (ac76808e4), unless noted. Benchmarks use 33 deterministic
tasks at temperature=0, seed=1.

---

## Scoring Quick Reference

| Column | Meaning |
|--------|---------|
| **Pass** | Tasks passed out of eligible (SKIPPED_CTX excluded) |
| **Skill** | Highest consecutive tier where the model passes *all* tasks L1 through LN |
| **Peak** | Highest individual level where the model passes *all* tasks at that level (ignores lower-level gaps) |
| **tok/s** | Average generation throughput across all tasks at that context size |

Task difficulty: L1 = trivial edits · L2 = simple logic · L3 = multi-file/data tasks · L4–L5 = complex algorithms · L6 = from-scratch game backend architecture.

Infrastructure failures (`SKIPPED_CTX`, `TOOL_ERROR`, `CTX_TRUNCATED`) are excluded from scoring and do not penalise a model's tier.

---

## Runner Guide

Choose your runner based on the use case:

**Ollama** — easiest to install and use; good enough for daily driving.
Handles model lifecycle automatically. Roughly 2–3× slower than llama-server
for the same model on the same hardware. Use it when convenience matters more
than throughput. Context window is managed automatically but you have less
control over KV quantization.

**llama-server** (llama.cpp) — the recommended production runner for
everything in this document. Faster than Ollama, precise control over KV cache
quantization (`f16`/`q8_0`/`q4_0`), flash attention, batch sizes, and per-model
context caps. Required when KV precision matters (see python_hashmap canary
note below). All benchmark numbers in this document are from llama-server.

**vLLM** — required for tensor parallelism across two or more GPUs. Use it
for 70B+ models or any 32B model that needs `tp=2`. Does **not** support MoE
GGUF files (qwen3-coder:30b-1m, gemma4:26b, noctrex, qwen3.5:35b all fail to
load). Works well with dense GGUF or native HuggingFace safetensors / GPTQ /
AWQ. For multi-GPU deployments, vLLM is the right choice for dense models.

---

## KV Cache Cheat Sheet

KV cache grows linearly with context length and is the main reason a model
that fits at 8k context starts to slow down or spill at 64k or 128k.

**Rule of thumb for dense 27–32B models with f16 KV:**

| Context | Approx KV | Fits in 24 GB after 19 GB model? |
|---------|-----------|----------------------------------|
| 8k      | ~0.8 GB   | Yes — fast                       |
| 32k     | ~3 GB     | Yes — fast                       |
| 64k     | ~6 GB     | Yes — fast                       |
| 128k    | ~13 GB    | No — spills to RAM, ~3–7× slower |

Switching to **q8_0 KV** halves these numbers and keeps 128k context in VRAM
on 24 GB, but some models (specifically `python_hashmap` on 27B dense models)
fail with a precision-boundary error. Use f16 KV for 27B dense models;
q8_0 KV is safe for MoE and for 32B models with larger weight-to-KV ratios.

**MoE models** (qwen3-coder:30b-1m, gemma4:26b, qwen3.5:35b) have the same
KV size as an equivalent-width dense model despite being faster — only the
weight forward pass is sparse, not the KV cache.

---

## 16 GB VRAM

*Representative hardware: RTX 3080 10 GB (too small), RTX 4080 16 GB, RTX 3080 Ti 12 GB*

At 16 GB, you can run models up to roughly 13–14 GB and still have meaningful
KV cache headroom. Models at ~15 GB will fit but leave only ~1 GB for KV —
fine for short coding prompts, unusable for retrieval tasks.

### Top 5 for 16 GB

| Rank | Model | Size | tok/s | Score | Best For |
|------|-------|------|-------|-------|----------|
| 1 | **noctrex-qwen3.6:35b** | ~13 GB | ~119 | 31/33 | Best-quality coder; ⚠ Ampere required |
| 2 | **qwen3-coder:30b-1m** | ~15 GB | ~150 | 30/33 | Fastest perfect coder; tight fit |
| 3 | **qwen2.5-coder:14b** | ~9 GB | ~68 | ~24/33 | Best balance of size, speed, context |
| 4 | **gpt-oss:20b** | ~12 GB | ~197 | 22–26/33 | Fastest raw throughput; variable results |
| 5 | **devstral-small-2** | ~15 GB | ~42 | ~28/33 | Agentic/instruction-following; tight fit |

#### noctrex-qwen3.6:35b (MoE MXFP4, ~13 GB)
The single best coding model that fits in 16 GB — 31/33 and 19/19 coding
perfect. MXFP4 quantization gives excellent quality at a tiny footprint.
**Requires an Ampere or newer GPU** (RTX 3090, RTX 4080, RTX 4090, A100).
Leaves ~3 GB for KV: comfortable up to ~32k context, fast above that at ~8k.
Not suitable for large context retrieval tasks on 16 GB.

**Caveats:** Ampere-only (MXFP4 format). MoE GGUF — use llama-server, not vLLM.
Disable spec decoding flags; MTP head is present but should not speculate.

**Runner:** llama-server only (vLLM cannot load MoE GGUF). Ollama for casual use.

#### qwen3-coder:30b-1m (MoE Q4_K_M, ~15 GB)
Perfect coding (19/19) at the fastest available throughput (~150 tok/s on
24 GB; expect ~120 tok/s on 16 GB given tighter fit). On a 16 GB card this
leaves only ~1 GB for KV — enough for coding tasks (prompts ≤ 4k tokens),
too small for context-heavy retrieval or long agentic sessions.
Despite the "1M context" label, that context window is not usable at 16 GB.

**Caveats:** ~1 GB KV at 16 GB limits useful context to ~4k tokens. MoE GGUF —
llama-server only. Does not improve from-scratch architecture tasks over the
base variant.

**Runner:** llama-server (best speed). Ollama available but ~3× slower.

#### qwen2.5-coder:14b (Dense Q4_K_M, ~9 GB)
The most versatile choice at 16 GB. At ~9 GB it leaves ~7 GB for KV,
supporting ~64k context comfortably. Good coding ability (~68 tok/s), solid
at L1–L3 tasks, starts to show limits at L4–L5 complex algorithms.
The right pick if you need both coding and context retrieval on the same 16 GB card.

**Caveats:** Weaker than 27–30B models on L4/L5 tasks. q8_0 KV is safe for this size.

**Runner:** Ollama or llama-server, both work well. vLLM works (dense GGUF).

#### gpt-oss:20b (Dense Q4_K_M, ~12 GB)
The fastest model in this tier at ~197 tok/s. Generates verbose reasoning in
plain text (not a formal thinking model) which sometimes helps and sometimes
exhausts the token budget. Results vary **22–26/33** between identical runs —
reasoning length is non-deterministic at temperature=0. A confirmed retrieval
bug at 64k context (returns RC-5000 instead of the correct value).
Good for rapid iteration where you want fast drafts, less good when you need
reproducibility.

**Caveats:** Non-deterministic results. 64k retrieval bug. Reasoning preamble
can exhaust token budget on L3+ tasks — use `--num-predict 8000` minimum.

**Runner:** Ollama or llama-server. Not recommended as a reference benchmark model.

#### devstral-small-2 (Dense 24B Q4_K_M, ~15 GB)
Mistral's instruction-tuned coding model, fine-tuned for agentic and
multi-step coding tasks. ~42 tok/s on 24 GB hardware; expect similar on 16 GB.
Tight fit (~1 GB KV at 16 GB) — effectively coding-only at this VRAM level.
Good l6_full from-scratch score (38/40), strong multi-step instruction following.

**Caveats:** Tight KV headroom at 16 GB. q8_0 KV is fine (no precision issue).

**Runner:** llama-server preferred (2.6× faster than Ollama for this model).

---

## 24 GB VRAM

*Representative hardware: RTX 3090 24 GB, RTX 4090 24 GB*

The sweet spot for local LLMs as of May 2026. All sub-20 GB models run fully
VRAM-resident with comfortable KV headroom. Models at 20–22 GB fit but leave
limited KV for large context windows.

### Top 5 for 24 GB

| Rank | Model | Size | tok/s | Score | Skill | Peak | Best For |
|------|-------|------|-------|-------|-------|------|----------|
| 1 | **noctrex-qwen3.6:35b** | ~13 GB | 119 | 31/33 | L5 | L5 | Best overall quality; ⚠ Ampere |
| 2 | **qwen3-coder:30b-1m** | ~15 GB | 150 | 30/33 | L4 | L5 | Fastest coder; no special GPU |
| 3 | **qwen3.6:27b** | ~19 GB | 37 | 31/33 | L5 | L5 | Best dense model; f16 KV required |
| 4 | **gemma4:26b** | ~17 GB | 110 | ~29/33 | L4 | L6 | Fast generalist; MoE caveat |
| 5 | **qwen3.5:35b** | ~21 GB | 147 | ~28/33 | L3 | L5 | Best reasoning/thinking |

#### noctrex-qwen3.6:35b (MoE MXFP4, ~13 GB, ~119 tok/s)
Top of the leaderboard at 31/33 and 19/19 coding perfect. The ~13 GB
footprint leaves ~11 GB for KV — comfortably handles 128k context with
room to spare. The MXFP4 precision preserves quality that Q4_K_M quantization
loses on precision-sensitive tasks. Passes both `csv_nordic_property` and
`node_csv_parser` where most MoE models fail.

**Caveats:** Requires Ampere+ GPU. MoE GGUF — llama-server only (vLLM fails
to load). No spec decoding flags.

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=f16, cache_type_v=f16,
flash_attn, batch_size=512, ubatch_size=128
```
**Runner:** llama-server.

#### qwen3-coder:30b-1m (MoE Q4_K_M, ~15 GB, ~150 tok/s)
Fastest model to achieve perfect coding (19/19). The 1M-context variant
behaves identically to the base on this benchmark — the extended context
window requires 1M tokens of KV which is not achievable on 24 GB. Practical
max context at 24 GB is ~32k (comfortable) or ~64k (functional).
An outstanding choice for automated coding workflows where speed matters.

**Caveats:** Fails `node_para_entities` (L6 step 3) — MoE expert routing
breaks the multi-step entity logic (same limitation as other MoE models).
Fails csv_nordic (multi-step data task, MoE limitation). The "1M context"
label refers to architecture max, not practical VRAM capacity.

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=f16, cache_type_v=f16,
flash_attn, batch_size=512, ubatch_size=128
```
**Runner:** llama-server (also available via Ollama at ~3× lower throughput).

#### qwen3.6:27b (Dense Q4_K_M, ~19 GB, ~37 tok/s)
The best dense model at 24 GB. Matches noctrex at 31/33 despite running at
~3× lower speed. Passes everything noctrex passes and is the only dense model
in the 24 GB tier. Dense architecture gives it a reasoning coherence advantage
on multi-step data tasks (`csv_nordic_property`, `node_csv_parser`) that MoE
models miss.

**f16 KV is required** — q8_0 KV causes a precision-boundary failure on
`python_hashmap` (the model omits `_EMPTY = None` from the tombstone hash map).
This costs speed at 128k context: f16 KV spills heavily at 131k tokens,
dropping to 6.8 tok/s vs ~18 tok/s with q8_0. Accept this trade-off; the
alternative is a silent correctness failure on algorithmic tasks.

Context window guide at 24 GB with f16 KV:

| Context | Speed | Notes |
|---------|-------|-------|
| 8k | 37 tok/s | Fast |
| 32k | 35 tok/s | Fast |
| 64k | 33 tok/s | Fast |
| 128k | 7 tok/s | Slow — f16 KV spills; passes within 3600s timeout |

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=f16, cache_type_v=f16,
flash_attn, batch_size=512, ubatch_size=128
```
**Runner:** llama-server (Ollama also works; both require f16 KV — Ollama uses
its own internal format which avoids the q8_0 issue automatically).

#### gemma4:26b (MoE Q4_K_M, ~17 GB, ~110 tok/s)
Google's mixture-of-experts model with only 4B active parameters. Extremely
fast for its size. Excellent from-scratch architecture tasks (39/40 on the
full Paratrooper game backend). Generates a verbose preamble before code on
most tasks — requires `--num-predict 8000` to avoid budget exhaustion.

Fails `csv_nordic_property` (multi-step data filtering — MoE limitation) and
likely fails `node_csv_parser` on the same grounds. If your workload involves
complex analytical data processing, prefer qwen3.6:27b. For architectural
reasoning, generalist tasks, and fast responses, gemma4:26b excels.

**Caveats:** Verbose preamble on complex tasks — always use `--num-predict 8000`.
MoE GGUF — llama-server only. L6 step 3 fails (node_para_entities: preamble
exhausts budget at that prompt size even with 8000 tokens).

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=f16, cache_type_v=f16,
flash_attn, batch_size=512, ubatch_size=128
```
**Runner:** llama-server. Ollama available.

#### qwen3.5:35b (Thinking MoE Q4_K_M, ~21 GB, ~147 tok/s)
The best reasoning/thinking model for 24 GB. Wraps all answers in `<think>`
tags and reasons before producing output. Outstanding on complex architectural
tasks (38/40 l6_full — the only model to pass L6 step 3 in a 5-model coding
comparison). Over-reasons on simple tasks, consuming the token budget on
trivial problems — use `--num-predict 16000` for algorithmic tasks,
`--num-predict 8000` is borderline for complex ones.

At ~21 GB it leaves only ~3 GB for KV, limiting practical context to ~32k.
Passes 128k context at 104 tok/s because retrieval questions are answered
quickly before the reasoning budget runs out.

**Caveats:** `thinking` flag required in model config. Reasoning exhausts budget
on `python_hashmap` even at 16000 tokens — consider 24000 for that task.
~21 GB leaves little KV headroom; 64k+ context for long agentic sessions is
impractical. q8_0 KV is fine at this size.

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=f16, cache_type_v=f16,
flash_attn, batch_size=512, ubatch_size=128, thinking
```
**Runner:** llama-server. Ollama available.

---

## 32 GB VRAM

*Representative hardware: RTX 6000 Ada 48 GB (more below), A6000 48 GB, or consumer RTX 5090 32 GB*

At 32 GB the main new arrivals are the 32B-parameter dense models that barely
didn't fit at 24 GB: `qwen2.5-coder:32b`, `qwq:32b`, and `deepseek-r1:32b`.
All 24 GB models also run here with substantially more KV headroom —
`qwen3.6:27b` can now comfortably reach 128k without spilling.

### Top 5 for 32 GB

| Rank | Model | Size | tok/s est. | Score | Best For |
|------|-------|------|-----------|-------|----------|
| 1 | **noctrex-qwen3.6:35b** | ~13 GB | ~119 | 31/33 | Best quality; Ampere required |
| 2 | **qwen2.5-coder:32b** | ~20 GB | ~36 | 19/24† | Long-context coding; 64k+ unlocked |
| 3 | **qwq:32b** | ~22 GB | ~30–40 | TBD | Strongest reasoning; impractical at 24 GB |
| 4 | **deepseek-r1:32b** | ~20 GB | ~29 | 18/19 coding | Reasoning + coding; avoids budget issues |
| 5 | **qwen3.6:27b** | ~19 GB | ~37 | 31/33 | Dense best; 128k now fast |

† 19/24 eligible — 3 tasks SKIPPED_CTX (context_64k, context_128k) on 24 GB because
weights leave insufficient KV. On 32 GB all context tasks are available.

#### qwen2.5-coder:32b (Dense Q4_K_M, ~20 GB, ~36 tok/s)
The coding-specialist upgrade from qwen2.5-coder:14b. At ~20 GB weights on a
32 GB card there is ~12 GB for KV — comfortable at 64k context (~6 GB KV)
with room for 128k depending on KV quantization. Passes all 19 coding tasks
cleanly on 24 GB (no context tasks); unlocks the full 33-task set at 32 GB.
A direct alternative to qwen3.6:27b for coding-heavy workloads.

**Caveats:** On 24 GB, context_32k and above timeout (KV overflow); 32 GB
required to unlock long-context use. q8_0 KV is appropriate at this size —
no python_hashmap precision issue confirmed.

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=q8_0, cache_type_v=q8_0,
flash_attn, batch_size=512, ubatch_size=128, max_ctx=65536
```
**Runner:** llama-server or vLLM (dense GGUF — vLLM works here).

#### qwq:32b (Dense Q5_K_M, ~22 GB, ~30–40 tok/s est.)
Qwen's strong reasoning model. At Q5_K_M (~22 GB) on a 24 GB card it
thrashes — KV cache has under 2 GB headroom, the server silently caps
context to 32k, and throughput collapses to ~6 tok/s. On 32 GB it becomes
genuinely usable: ~10 GB for KV supports 64k context at reasonable speed.
Competitive with deepseek-r1 on reasoning tasks.

**Caveats:** Q5_K_M preferred over Q4_K_M for reasoning quality. Need
`--num-predict 12000+` for thinking models. On 32 GB use `max_ctx=65536`
for safety. Results not yet benchmarked on this harness at 32 GB (24 GB
result: 11/24, 6 tok/s — hardware-limited, not capability-limited).

**Runner:** llama-server. vLLM works (dense GGUF).

#### deepseek-r1:32b (Thinking Dense Q4_K_M, ~20 GB, ~29 tok/s)
DeepSeek's R1-Distill-Qwen-32B is a strong reasoning model with transparent
`<think>` chain-of-thought. 18/19 coding at 31.4 tok/s on 24 GB with
`max_ctx=32768`. One confirmed capability gap: `python_expr_eval` (enters an
infinite "code is correct. But..." reasoning spiral — not fixable by increasing
token budget). Strong on multihop retrieval tasks (~21 tok/s at 32k).

At 32 GB, set `max_ctx=65536` to unlock context_64k and improve multihop.
The `max_ctx=32768` hard cap on 24 GB was a hardware constraint, not an
architecture limit.

**Caveats:** `python_expr_eval` is a structural capability gap — avoid that
specific task. `thinking` flag required. On 32 GB use `max_ctx=65536`.

**Optimal settings (llama-server):**
```
ngl=999, no_mmap, cache_type_k=q8_0, cache_type_v=q8_0,
flash_attn, batch_size=512, ubatch_size=128, max_ctx=65536, thinking
```
**Runner:** llama-server or vLLM (dense GGUF).

#### qwen3.6:27b at 32 GB
The same model as in the 24 GB tier, but with ~13 GB of KV headroom.
This means 128k context runs at full speed (no spill) — the 6.8 tok/s
bottleneck that occurs at 24 GB disappears. With q8_0 KV (now safe since
you have headroom to spare) 128k becomes practical at ~18+ tok/s.

At 32 GB you can switch to q8_0 KV for 128k workloads if you accept the
python_hashmap trade-off, or keep f16 KV for algorithmic correctness.

---

## 2× 24 GB VRAM (48 GB total)

*Representative hardware: 2× RTX 3090 24 GB, 2× RTX 4090 24 GB*

Tensor parallelism across two 24 GB cards opens the 40–70B parameter class.
Use **vLLM** with `tp=2` for dense models (llama-server tensor parallelism
support is more limited). MoE models that fit in 24 GB still run well on a
single card — there is no benefit to splitting a 13 GB model across two GPUs.

All benchmark numbers in this section are **projected** based on model size
and single-GPU data; direct 2-GPU benchmarks not yet collected.

### Top 5 for 2× 24 GB (48 GB)

| Rank | Model | Size | tok/s est. | Best For |
|------|-------|------|-----------|----------|
| 1 | **qwen3-coder-next** | ~46 GB | ~35–40 | New-gen coder, 19/19 perfect; dense 72B |
| 2 | **llama3.3:70b** | ~40 GB | ~25–35 | Strong generalist 70B; first 70B result |
| 3 | **gpt-oss:120b** | ~60 GB | ~35–45 | Full GPU thinking model; RAM-bound at 24 GB |
| 4 | **qwen3-coder:30b-1m** | ~15 GB | ~150 | Still single-GPU; now with 30+ GB KV headroom |
| 5 | **noctrex-qwen3.6:35b** | ~13 GB | ~119 | Still single-GPU; extreme context headroom |

#### qwen3-coder-next (Dense ~72B Q4_K_M, ~46 GB, ~35–40 tok/s projected)
The headline addition for dual-GPU. Benchmarked at 16.6 tok/s on a single 24 GB
card (52% RAM-resident) — already achieving perfect coding (19/19). On 48 GB
both cards it would be fully VRAM-resident, expected to run at ~35–40 tok/s.
At that speed with perfect coding it would become the strongest practical coder
in the entire lineup. The 4-shard GGUF loads automatically from the first shard
filename when using llama-server.

**Caveats:** Not yet benchmarked with `tp=2`. vLLM multi-shard GGUF support
untested; recommend llama-server for initial runs. Use `cache_type_k=f16` to
match the single-GPU confirmed settings.

**Optimal settings (llama-server, 2-GPU):**
```
ngl=999, no_mmap, cache_type_k=f16, cache_type_v=f16,
flash_attn, batch_size=512, ubatch_size=128
```
**Runner:** llama-server (preferred until vLLM multi-shard GGUF validated).

#### llama3.3:70b (Dense Q4_K_S, ~40 GB, ~25–35 tok/s projected)
Meta's 70B instruction-tuned model. Strong generalist capability; confirmed
9/10 coding tasks on a single 24 GB card at 2.5 tok/s (CPU-bound at ngl=45).
Fully GPU-resident on 48 GB via `tp=2`. Pre-configured in `models/default.vllm`.
Tokenizer is gated — set `HF_TOKEN` environment variable.

**Caveats:** Not yet benchmarked with `tp=2`. Gated tokenizer (Meta licence).
`max_ctx=32768` recommended for the first run.

**Runner:** vLLM with `tp=2` (pre-configured in `models/default.vllm`).

#### gpt-oss:120b (MXFP4 MoE, ~60 GB, ~35–45 tok/s projected)
Currently the RAM-bound thinking model on the test rig at ~17 tok/s. On 48 GB
it would be fully GPU-resident (60 GB > 48 GB — still spills slightly, but
dramatically better). On a true 64 GB setup it would be fully resident.
Strong thinking model when it has budget; non-deterministic reasoning length
remains a caveat regardless of hardware.

**Caveats:** ~60 GB weights — still partially RAM-bound on 48 GB; fully
resident on 64 GB. Variable reasoning length. `thinking` flag required.
`n_cpu_moe=35` offloads MoE expert layers to CPU — may not be needed at 48 GB.

**Runner:** llama-server (MoE GGUF; vLLM cannot load MoE GGUF).

#### qwen3-coder:30b-1m at 2× 24 GB
No change in model performance — it already runs fully GPU-resident on a
single 24 GB card. The benefit on 48 GB is KV headroom: ~33 GB available for
KV, enabling the 1M context window to actually be used (1M tokens of KV at
f16 is ~100 GB — still beyond reach, but 200k context becomes practical).

#### noctrex-qwen3.6:35b at 2× 24 GB
Same situation — single-card model, no speed gain from 2 GPUs. The second
card frees KV headroom for very long context windows. Useful for embedding
entire large codebases in context.

---

## 2× 32 GB VRAM (64 GB total)

*Representative hardware: 2× RTX 6000 Ada, 2× A6000, 2× RTX 5090 (projected)*

At 64 GB, all models in this document fit fully GPU-resident with substantial
KV headroom. The main additions over 48 GB are gpt-oss:120b fully resident
and the ability to use 1M+ context windows on smaller models.

### Top 5 for 2× 32 GB (64 GB)

| Rank | Model | Size | tok/s est. | Best For |
|------|-------|------|-----------|----------|
| 1 | **qwen3-coder-next** | ~46 GB | ~40–50 | Perfect coder; 20+ GB KV headroom |
| 2 | **gpt-oss:120b** | ~60 GB | ~40–55 | Fully resident thinking model |
| 3 | **llama3.3:70b** | ~40 GB | ~30–40 | Strong 70B generalist |
| 4 | **Devstral-2-123B** | ~46 GB | ~25–35 | Large agentic model (not yet tested) |
| 5 | **qwq:32b or deepseek-r1:32b** | ~20–22 GB | ~60+ | Single-card; massive KV headroom |

*All numbers projected; no direct 64 GB benchmarks collected.*

#### qwen3-coder-next at 2× 32 GB
Fully resident with ~18 GB of KV headroom — enough for ~64k context at f16 KV
or ~128k at q8_0. The strongest coding model in the lineup with capacity for
very long context windows. Likely the best coding model available locally by a
significant margin once the hardware arrives.

#### gpt-oss:120b (MXFP4 MoE, ~60 GB, ~40–55 tok/s projected)
Fully GPU-resident for the first time. As a thinking model it reasons through
problems step by step; the non-deterministic reasoning length caveat remains
but the throughput improvement (from 17 tok/s RAM-bound to 40+ tok/s GPU)
makes it practical for daily use. Exceptional at complex multi-step reasoning,
weak on simple tasks (over-reasons and exhausts budget). Not recommended as
a coding-only model — qwen3-coder-next is faster and specialised.

#### Devstral-2-123B (not yet benchmarked)
Mistral's 123B model (December 2025). At ~46 GB at Q4_K_M (estimated) it
fits in 64 GB with meaningful KV headroom. Not benchmarked on this harness;
candidate for evaluation when hardware arrives. Expected to excel at agentic
multi-step coding workflows given the Devstral-Small-2 lineage.

---

## Cross-Cutting Observations

### Dense models beat MoE on multi-step analytical tasks

Confirmed across two model generations:

| Task | MoE result | Dense equivalent | Dense result |
|------|-----------|-----------------|--------------|
| csv_nordic_property | qwen3.5:35b FAIL | qwen3.5:27b | PASS |
| csv_nordic_property | qwen3.6:35b FAIL | qwen3.6:27b | PASS |
| csv_nordic_property | gemma4:26b FAIL | gemma4:31b | PASS |
| node_csv_parser | qwen3.6:35b FAIL | qwen3.6:27b | PASS |
| L6 step 3 entities | gemma4:26b FAIL | gemma4:31b | PASS |
| L6 step 3 entities | qwen3-coder:30b FAIL | qwen3.6:27b | PASS |

The cause is likely expert routing in MoE breaking the coherent multi-step
context needed for complex data filtering or multi-entity game logic. For
these tasks, pick a dense model. For pure coding speed, MoE wins.

### The python_hashmap precision canary

The `python_hashmap` task (open-addressing hash map with tombstone deletion)
is acutely sensitive to quantization precision. With q8_0 KV cache or GPTQ
INT4 (C4 calibration), 27B dense models omit `_EMPTY = None` from the
module-level definitions — a single wrong token at a precision boundary.

**Rule:** Use `cache_type_k=f16, cache_type_v=f16` for 27B dense models.
For MoE and 32B+ models, q8_0 KV is safe.

### Thinking models need budget

Models with formal reasoning (`<think>` tags): qwen3.5:35b, deepseek-r1:32b,
qwq:32b, gpt-oss:120b, phi4-reasoning-plus (incompatible — loops forever).

Set `--num-predict 8000` as a minimum. Complex algorithmic tasks (L4/L5)
benefit from 12000–24000. Reasoning tokens consume the budget before the
answer appears — if a task produces NO_BLOCKS or TRUNCATED, increase the
budget before concluding it is a capability failure.

### MoE spec decoding breaks determinism

Models with MTP (Multi-Token Prediction) heads — carnice:35b, noctrex-qwen3.6:35b,
and any `MTP` GGUF from bartowski (build 9180+) — have the MTP head bundled in
the GGUF. Loading the GGUF is fine; **do not** pass `--spec-type draft-mtp`.
Spec decoding with temperature=0 is non-deterministic and regresses quality.
The benchmark confirmed python_hashmap fails with spec decoding enabled on
the carnice variant.

### The l6_full ceiling

No model has ever passed test 33 ("freefall paratrooper landing kills landed
paratroopers below") in the from-scratch game backend task. The rule is
explicit in the stub. This is a capability gap: models implement the standard
landing routine but miss the secondary same-tick crush check. The best scores
are 39/40 (gemma4:26b, qwen3.6:35b-A3B). Scores of 38/40 are common for
strong models. Not a spec ambiguity; do not change the test.

---

## Runner Quick Reference

| Model type | Ollama | llama-server | vLLM |
|------------|--------|-------------|------|
| Any MoE GGUF | ✓ (slower) | ✓ (best) | ✗ (fails to load) |
| Dense GGUF ≤ 32B | ✓ | ✓ (best) | ✓ |
| Dense GGUF 40–70B single-GPU | ✓ (slow) | ✓ | ✓ |
| Dense 70B+ with tp=2 | ✗ | Limited | ✓ (best) |
| GPTQ / AWQ / safetensors | ✗ | ✗ | ✓ |
| Need precise KV quant control | ✗ | ✓ | Partial |
| Just want to try a model | ✓ | — | — |

---

## Appendix: Benchmark Task Groups

| Group | Tasks | Difficulty | Notes |
|-------|-------|-----------|-------|
| coding | 19 tasks | L1–L5 | Python, Node, .NET, AWK, Java |
| context | 6 tasks | L1–L3 | 8k / 16k / 32k / 64k / 128k / 256k needle |
| multihop | 3 tasks | L2–L3 | Two-hop retrieval; distractor variant |
| l6 (stepped) | 4 tasks | L3–L6 | Paratrooper game backend built up across 4 steps |
| l6_full | 1 task (40 sub-tests) | L6 | Same game from scratch; 39/40 is the current ceiling |

*Generated 2026-05-29 from ollama-code-bench benchmark data.*
