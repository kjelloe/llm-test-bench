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
  Use a reasonably fresh checkout (post-2026-09-06) so the Blackwell-unlock fix is included —
  an older pinned release may still carry the old restriction.
- Verify the GPU is actually recognized before doing anything else:
  ```bash
  nvidia-smi --query-gpu=index,name,compute_cap,memory.total --format=csv
  ```
  Blackwell should report compute capability 12.0 (e.g. RTX 5070 Ti and similar RTX 50-series
  parts). If CUDA/driver isn't picking the card up correctly, nothing below will work — confirm
  this first.

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
vllm serve bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q4_K_M

# 2×16 GB, tensor parallel
vllm serve bartowski/Qwen2.5-Coder-32B-Instruct-GGUF:Q4_K_M --tensor-parallel-size 2
```

No `--quantization gguf` patch flag needed — that requirement is obsolete now that GGUF support
lives in the plugin, not in-tree. Both of these are plain dense Qwen2.5 checkpoints, so none of
the MoE-specific plugin quirks apply (K-quant-vs-I-Matrix kernel selection, `--hf-config-path`
for Qwen3.5-MoE) — those only matter once you branch out past this pair.

## 4. Smoke test

```bash
curl -s http://127.0.0.1:8000/v1/completions \
  -H 'content-type: application/json' \
  -d '{"model":"bartowski/Qwen2.5-Coder-14B-Instruct-GGUF","prompt":"def fib(n):","max_tokens":32}'
```

Expect a real completion, not an error. If this repo (`llm-test-bench`) is cloned onto the same
box, its own harness can drive the full task suite instead of a manual curl — but note two
things first: `lib/vllm_client.py` always **spawns and manages its own `vllm serve` subprocess
locally**, with no remote-host mode, so this only works run directly on the RTX 50xx machine, not
pointed at it from elsewhere; and the existing `models/*.vllm` entries for these two models
(`32gb.vllm`, `2x24gb.vllm`, `default.vllm`) **predate the GGUF-plugin migration** — they use the
old `--load-format gguf` convention where `hf:` names a *tokenizer* repo (`Qwen/Qwen2.5-Coder-*-
Instruct`, the official safetensors repo) and expect the GGUF file to already exist locally under
whatever name is listed, fetched some other way. That's a different setup than the plugin's own
`vllm serve <gguf-repo>:<quant>` convention this doc uses above. Don't assume those file entries
work unmodified against the plugin — either add fresh entries pointing `hf:` at bartowski's GGUF
repos (matching §2/§3 above) and verify the params still make sense for the plugin's loader, or
skip the harness for this first pass and just use the plain `vllm serve` commands in §3.

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

## 6b. Second experiment on this box: Qwen3.8-27B via vLLM-native quants

Once §1-5 confirm the box works at all (the Qwen2.5-coder pair above), the more interesting test
is `Qwen3.8-27B` — architecturally identical to this repo's own extensively-tested `qwen3.8:27b`
(Gated DeltaNet hybrid, confirmed via `config.json`: `Qwen3_5ForConditionalGeneration` /
`qwen3_5`), but tried here in vLLM-native quant formats instead of GGUF. For 2×16 GB:

- **Try first**: `QUASAR-QAT/Qwen3.8-27B-QUASAR-NVFP4` (20.6 GB, best VRAM headroom, `vllm`-
  tagged, published eval results, native Blackwell NVFP4 acceleration).
- **Second try** if quality disappoints: `unsloth/Qwen3.8-27B-NVFP4` (23.4 GB, but VL-capable —
  carries unused vision-tower weight for a text-only coding use case).
- Skip `Qwen/Qwen3.8-27B-FP8` (official, 30.9 GB) for this VRAM budget — leaves ~1 GB across the
  whole 32 GB, no real context room; that one wants a single 32 GB+ card instead.

None of these are GGUF — plain `vllm serve <repo>` should work directly, no plugin needed (the
GGUF plugin only matters for the GGUF path in §1-5). Full rationale, sizes, and the source of
this lead (a Reddit thread) in `next-runs.md`'s "Reddit-sourced vLLM-native Qwen3.8-27B quant
leads" section.

**Worth testing directly, not assuming**: multiple people in that thread claim vLLM flatly
doesn't support GGUF and to not bother — contradicts this repo's own source-verified
`vllm-gguf-plugin` finding from §1-5's setup. This box is the first opportunity to actually
resolve that disagreement instead of trusting either side.

## 7. Once there are results

Cascade findings back into `CLAUDE.md` (replace the "not yet vLLM-tested" caveat on the
recommendation), `next-runs.md`, and memory — same pattern used for every other finding in this
project.
