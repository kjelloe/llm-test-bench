### Working Agreement for AI Assistants (Claude / local model)

You are helping build a local benchmark harness repo. Optimize for correctness, reproducibility, and maintainability.

#### Repository Principles

- Prefer robust, simple parsing and strict validation.
- Fail loudly with categorized errors instead of "best-effort" silent behavior.
- Keep tasks deterministic and small.
- Do not add large dependencies unless clearly justified.

#### Code Style

- Python 3.12 compatible, stdlib-first.
- Small functions, clear names, type hints where helpful.
- Use `subprocess.run(..., timeout=...)` for all external commands.
- Never shell out with `shell=True`.

#### Safety & Determinism

- Default `temperature=0` and `seed=1`.
- `num_predict` default is 400 for simple/instruct models. Use 8000+ for thinking models
  (qwen3.5, gpt-oss:120b, deepseek-r1, etc.) — their reasoning tokens consume the budget
  before the answer. All 19 coding tasks now have `min_predict` set (8000–24000) so they
  floor the budget even when `--num-predict` is not passed; previously python_safe_div,
  dotnet_sas, python_multifile_rename, python_ledger_bug, node_debounce,
  python_merge_intervals, awk_csv_stats, and java_word_freq had `min_predict=None` and
  silently failed with NO_BLOCKS TRUNCATED for thinking models on bare `./run.sh` calls.
  `compare.sh` sets `--num-predict 8000` explicitly; 4800 was insufficient
  for gemma4:26b verbose preamble tasks and gpt-oss:20b complex tasks; 2400 was too few for
  qwen3.5:35b on basic tasks; 1200 was too few for gpt-oss:120b on complex tasks (CSV parser
  ran out mid-reasoning). Note: gpt-oss:20b and gemma4:26b are NOT thinking models — do not
  mark them `thinking` in model files; the "After your reasoning" prefix causes planning loops.
  - **gpt-oss:20b "semi-thinking"**: generates verbose reasoning in plain text output (not
    `reasoning_content`) on L2+ tasks; exhausts 4800 token budget before BEGIN_FILE on
    python_expr_eval and python_tokenizer; needs 8000+ for those tasks (compare.sh now uses
    8000). At 8000 tokens the reasoning length is non-deterministic — in the 2026-05-25
    official compare.sh run, verbose reasoning exhausted the budget before BEGIN_FILE on
    python_minheap, python_dijkstra, python_hashmap, python_tokenizer, and node_para_combat
    → 22/33 (down from 26/33 in the 2026-05-24 run; same root cause, different reasoning
    length). Skill <L1 because context_64k also fails with a wrong answer (TESTS_STILL_FAIL
    — retrieves RC-5000 instead of correct value; passes at context_32k and context_128k;
    appears to be a retrieval failure specific to that context depth, not a token budget
    issue). Results for this model are inherently variable between runs.
    **CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 4/6 — ctx_8k *82.6 (7.6s),
    ctx_16k *75.7 (10.9s), ctx_32k *71.5 (15.8s), ctx_128k *39.3 (81.3s) PASS; ctx_64k
    TESTS_STILL_FAIL *55.4 (36.1s — consistent with prior known wrong-retrieval at this depth);
    ctx_256k CTX_TRUNCATED — architecture hard limit n_ctx_train=131072 (same as qwen2.5-coder:32b);
    max_ctx=262144 was wrong, corrected to max_ctx=131072 in 2x24gb.txt. GPU1 max 63°C.
    **MULTIHOP (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 2/3 — forward PASS *13.4 tok/s
    (178.5s — verbose reasoning ~2380 tokens), reverse PASS *59.3 tok/s (23.1s), distractor
    FAIL TESTS_STILL_FAIL *71.9 tok/s (24.2s). Speed non-deterministic — same semi-thinking
    variability as coding tasks. GPU1 max 58°C.
    Adding `thinking` does NOT help — it causes a different planning loop. It is correctly
    left without the `thinking` flag.
  - **gemma4:26b verbose preamble**: generates a long task description + approach summary
    before BEGIN_FILE regardless of the system prompt; exhausts 4800 tokens on complex tasks
    (node_csv_parser, python_lru_cache, python_tokenizer, multihop_forward, csv_nordic_property).
    Needs 8000+ for L2+ tasks; compare.sh now uses 8000 which fixes many tasks.
    CONFIRMED 2026-07-22 (--num-predict 16000 candidate run): node_csv_parser STILL TRUNCATED at
    16000 tokens (135s, 119 tok/s — full 16k budget consumed by preamble + partial code); verbose
    preamble is structural and does not improve with higher budget. csv_nordic_property at 16k:
    TESTS_STILL_FAIL quickly (22s, ~2.6k tokens — capability gap, not budget issue).
    Also causes NO_BLOCKS on node_para_entities (L6 step 3): the step 3 prompt includes
    reference implementations for steps 1-2, making the context significantly larger;
    verbose preamble exhausts the budget before END_FILE even at 8000 tokens.
  - **qwen3.5:35b over-reasoning**: even python_hashmap at min_predict=16000 is exhausted
    by reasoning alone (wall 100s × 158 tok/s ≈ all 16000 tokens); consider 24000 for that task.
    Passes context_128k at 104.4 tok/s (2026-05-20 default run) — retrieval questions are
    answered quickly and don't exhaust budget. Budget exhaustion applies to coding tasks at
    131k context: thinking tokens fill the 8000 budget before BEGIN_FILE (response_truncated,
    plain-text reasoning emitted). Use 16000+ num_predict for coding tasks at large context.
    Despite over-reasoning on simpler tasks, achieves L6 4/4 on stepped tasks (2026-05-19,
    149 tok/s) — the only model to pass node_para_entities (step 3) in the coding5 set.
    In the default 7-model set (2026-05-20): gpt-oss:20b and qwen2.5-coder:14b also pass
    step 3, but gpt-oss:20b fails step 4 (NO_BLOCKS) and qwen2.5-coder:14b fails steps 1, 2,
    4. qwen3-coder:30b (now qwen3-coder:30b-1m in default.txt since 2026-05-24) fails step 3
    despite perfect 19/19 on coding tasks; the 1M variant has identical L6 behavior.
  - **carnice:35b MTP overhead**: MTP head causes ~4-5× speed penalty vs base qwen3.6 (41 tok/s
    coding-only, 27 tok/s full run with context, vs 134 tok/s base). Full 29-task run takes 96 min
    vs 10 min for qwen3.6. Context speed collapses to 6.2 tok/s at 128k (1504s) — slower than
    RAM-bound gpt-oss:120b (16.9 tok/s). Also prone to NO_BLOCKS on complex tasks (node_para_core,
    node_para_entities, csv_nordic_property, node_paratrooper, python_merge_intervals): verbose
    reasoning exhausts 8000-token budget before emitting BEGIN_FILE. python_merge_intervals
    specifically: 8000 tokens entirely consumed by reasoning at 270s even with min_predict=8000;
    needs ~12000+ for carnice on this task. 17/19 coding (2026-05-24) but impractical for any
    workload beyond short coding tasks on 24 GB.
    Spec decoding (--spec-type draft-mtp) disabled — harms determinism at temperature=0.
  - **qwen3-coder:30b partial-method-completion**: on tasks with "Do not modify any other
    method" instruction, may output just the class body and drop module-level declarations
    (DEFAULTS, mulberry32) — produces `ReferenceError: DEFAULTS is not defined` at runtime.
    Step 2 stub now includes explicit "Output the complete file" instruction. Otherwise
    achieves 15/15 on coding tasks; passes L6 step 4 (full scaffolding eliminates the issue).
- `--warmup` sends a 5-token dummy prompt to each model before the benchmark loop to force
  model load from RAM/disk. Eliminates the cold-start wall-time penalty on the first task
  (gpt-oss:120b first task was 399s cold vs 68s warm). Enabled by default in `compare.sh`.
- Default `--model-timeout` is 300s for `bench.py`. `compare.sh` sets `--model-timeout 1200`
  because large RAM-bound models (gpt-oss:120b) at ~1–2 tok/s need up to
  ~1200s for 1200 tokens; 300s causes spurious TOOL_ERROR timeouts on those models.
  Individual tasks may override with `model_timeout` on the Task dataclass (e.g. context_128k
  uses 3600s and context_256k uses 7200s because prompt-eval alone can exceed 1200s).
  Note: qwen3-coder:30b at context_128k (ctx=131072) on RTX 3090 24GB ran at 3.8 tok/s for
  1870s — KV cache for a 30B model at 131072 ctx fills ~24GB and partially spills. Within
  the 3600s per-task timeout but adds 31 minutes to the compare run.

#### Per-Model Benchmark Results

One row per (model, GPU config) — the same model can score differently across configs (see the
cross-GPU floating-point sensitivity rule below), so config is part of the key, not a footnote.
"—" = not run at that config. Coding/Web/L6-stepped/Multihop are "pass/total"; L6-full is the
single `node_paratrooper` from-scratch task (PASS/FAIL/untested); Context is the highest
successfully-reached ctx tier (not the per-tier speed breakdown, which is dropped except where a
specific tier's number is cross-referenced elsewhere in this file — those are called out in Notes).

| Model | Config | Coding | Web | L6-step | L6-full | Context | Multihop | tok/s | Notes |
|---|---|---|---|---|---|---|---|---|---|
| qwen3-coder:30b-1m | 2×24GB | — | — | — | — | 6/6 (256k) | 3/3 | 49.1 avg (ctx) | q8_0 KV. context_256k 13.6 tok/s — slower than quest:35b (52.4) and noctrex-qwen3.6:35b (46.1) at same ctx; "1M" long-context arch pays per-token overhead even at 256k despite smaller KV. multihop 56.1 avg. max_ctx=262144. |
| devstral-small-2 | 1×24GB | 17/19 | — | — | — | 5/6 (128k) | 3/3 | 54.6 (coding) | Mistral/lmstudio dense 24B Q4_K_M, q8_0 KV. FAILS: csv_nordic_property (L3), node_slugify (L2, genuine regex/casing capability gap, not format) → Skill L1. PASS incl. python_hashmap (L5, q8_0 KV fine on this non-qwen3.6/3.8 arch) + python_dijkstra. Speed 53.8–56.2 tok/s narrow range (dense). llama-server ~54 tok/s vs ollama ~17 tok/s (3.2×). |
| devstral-small-2 | 2×24GB | — | — | — | — | 5/6 (128k) | 3/3 | 26.8 (ctx) | 3.6× faster at ctx_128k vs single-GPU (18.6 vs ~5.2 tok/s). multihop 27.9 avg. Full profile: 17/19 coding + 5/6 ctx + 3/3 multihop, Skill L1 (node_slugify cap). max_ctx=131072 (256k SKIPPED_CTX). |
| qwen2.5:72b-q4 | 3×24GB | spot 6/10 | — | — | FAIL | — | — | 8.7 | REJECTED (below 8/10). bartowski Q4_K_M, 44.2 GB, tensor_split=1\|1\|1, q8_0 KV. PASS: safe_div, slugify, lru_cache, csv_nordic (346s), csv_parser, expr_eval. FAIL: tokenizer, **hashmap (genuine capability gap, not q8_0 precision — Qwen2.5-coder:32b passes hashmap at q8_0)**, node_para_core, paratrooper. csv_nordic+csv_parser PASS here proves the prior 48GB 4/8 failures were a ctx=16384 artifact, not a capability gap. 6× slower than gpt-oss:120b (55 tok/s) at lower quality; coding fine-tune (qwen2.5-coder:32b, 19/19) beats this larger instruct model. Not added to any model set. |
| llama3.3:70b | 2×24GB (4090+3090) | spot 5/7 | — | — | — | 32768 (confirmed safe) | — | 19.8 | CONFIRMED 2026-06-14, bartowski Q4_K_S (~37GB), tensor_split=1\|1, q8_0 KV, PCIe-bound (no NVLink). PASS: csv_nordic_property, python_tokenizer, node_para_core. FAIL: python_hashmap, node_csv_parser (TESTS_STILL_FAIL). ~11GB KV across both cards. |
| llama3.3:70b | 3×24GB (tensor_split=1\|1\|1) | spot 6/10 | — | — | — | — | — | 17.4 | CONFIRMED 2026-06-23, Q4_K_M (~40GB), q8_0 KV, max_ctx=65536. FAIL: node_csv_parser, python_hashmap, csv_nordic_property, node_para_core. **SKIPPED/not downloaded further** — dominated by qwen3-next:80b (better quality + faster on the same 72GB tier); kept as a reference config only, not promoted. |
| qwen2.5-coder:32b-q4 | 2×24GB | 19/19 | 4/4 | — | FAIL | 32768 (hard cap) | 3/3 | 36.5 | Full 33-task 2026-06-26: 28/33, Skill L2 (38-task scoring includes L6). CODING PERFECT incl. csv_nordic, csv_parser, expr_eval (where deepseek-r1:32b loops forever), dijkstra, para_turret/entities/combat. FAILS: node_para_core (L3 game-logic gap, shared with qwen3-next:80b, quest:35b), paratrooper (universal wall). **Context ceiling: server silently caps ctx=32768 regardless of max_ctx config, confirmed even at 72GB VRAM (3×24GB) — not a VRAM artifact, internal to GGUF metadata (likely RoPE/n_ctx_train).** context_64k/128k → CTX_TRUNCATED; 256k → SKIPPED_CTX. python_hashmap PASS at q8_0 KV (the q8_0 precision issue is specific to 27B dense, not 32B). Web 4/4 incl. fastapi (field_validator+.strip()). Added to 24gb.txt + 2x24gb.txt. |
| deepseek-r1:32b | 2×24GB | 18/19 | — | 3/4† | — | 4/6 (64k) | 3/3 | 31.4 (coding), 18.2 (multihop) | Q4_K_M ~20GB, max_ctx=32768 hard cap on 24GB. FAIL: python_expr_eval — infinite reasoning spiral ("code is correct. But..."), not fixable by budget/ctx. ctx_128k NO_BLOCKS (thinking exhausts 8000-budget at 128k prompt, ~1584 reasoning tokens at ctx_64k alone); ctx_256k SKIPPED_CTX (arch limit 131072). †L6-stepped not separately run; full 33-task score was 23/29 eligible (~29 tok/s, 2026-05-22). |
| qwq:32b | 1×24GB | — | — | — | — | — | — | ~6 | Q5_K_M ~22GB. Effectively unusable on 24GB — KV thrashing. 11/24 tasks pass. Server silently caps max_ctx 65536→32768 under VRAM pressure. Needs true 32GB; set max_ctx=32768 to avoid CTX_TRUNCATED. |
| codestral:22b | 1×24GB | — | — | — | — | hard 32k limit | FAIL | ~50 | Dense 22B ~14GB. 15/24. Hard architecture limit of 32k tokens (Codestral v0.1, baked into weights) — CTX_TRUNCATED on 64k/128k/multihop/distractor. No workaround. |
| mellum2:12b-thinking | 1×24GB | 13/19 | — | 2/4 | FAIL | SKIPPED_CTX ≥64k | 2/3 | 254.1 | JetBrains MXFP4 A2.5B, ~6.5GB, Ampere+ required. Full 33-task: 20/33, Skill L1. Fastest model at the time. FAILS: csv_nordic, node_slugify (L2, caps Skill), multifile_rename, node_debounce, dijkstra, **hashmap (hard ceiling for thinking models — 12000-token think budget entirely consumed, not fixable by budget)**. SURPRISE PASSES: node_para_core (where qwen2.5-coder:32b-q4 fails), node_csv_parser (where qwen3-next:80b/quest:35b fail), para_turret. Multihop: passes forward+distractor, fails reverse. |
| phi4-reasoning-plus:14b | 1×24GB | 0/13 | — | — | — | — | — | ~58 | INCOMPATIBLE — loops in reasoning planning phase, never emits BEGIN_FILE at any budget (confirmed 4800 and 12000). Trained for inline answers, not structured file blocks. Do not benchmark. |
| qwen3-next:256e | 2×24GB | spot 6/10 | — | — | FAIL | — | — | 93.1 | mradermacher Q4_K_M 23.3GB. REJECTED. PASS: safe_div, lru_cache, **csv_nordic (87.3, unusual for 23GB)**, tokenizer, expr_eval, **node_para_core (88.7, unusual)**. FAIL: node_slugify (regex bug, genuine capability gap, caps Skill L1), csv_parser (quoted-comma), hashmap (same L5 ceiling as other A3B), paratrooper. 256E routing unlocks csv_nordic+para_core but not the hashmap ceiling. |
| llama4-scout:17b | 1×24GB, 3×24GB | spot 7/10 | — | — | FAIL | 1/1 (128k, slow) | — | 3.3 (1GPU) / 10-29 (3GPU) | MoE 17B active/109B total, ~60GB hybrid, mostly CPU-bound on 24GB. 3×24GB spot CONFIRMED 2026-08-11: REJECTED. FAIL: csv_nordic (structural, 237s, not a timeout artifact), hashmap, paratrooper. PASS: csv_parser, expr_eval, node_para_core. Prior "19/24" was SKIP-inflated; real capability ≈7/10. Not worth 3x24gb.txt — same ~60GB footprint as gpt-oss:120b at far lower quality. |
| glm4.7-flash | 1×24GB | 17/19→18/19‡ | 3/4 | 4/4 | FAIL | 5/6 (128k)§ | 3/3 | 112 (2026-06-22) / 110.9 (33-task) / 56.7 (2×24GB ctx) | Zhipu/noctrex MXFP4, ~16GB, single RTX 4090. Full 33-task 2026-06-26: 29/33, Skill L4. FAILS: hashmap, dijkstra (both L5), paratrooper, context_256k (capability gap at 476s/45tok/s, not OOM). SURPRISE: passes para_entities+para_combat (full L6-stepped chain, one of the few compact single-GPU completers). Requires ./gpu-mode.sh single (else auto-splits across both GPUs). ‡REGRESSION 2026-07-23 (llama-server 10094, kq-mask #25370): python_config_loader FAIL (was PASS) — caps web/Skill at L1 on that binary; csv_nordic still PASS. §2×24GB context: 5/5 PASS 8k-128k at 56.7 avg (256k SKIPPED_CTX); tensor_split PCIe overhead makes single-GPU faster for this 16GB model (73.6/63.3 vs 56.7 at 64k/128k). Multihop 2×24GB: 3/3 at 70.5 avg. Added to 24gb.txt. |
| qwen3-30b:2507 | 1×24GB | 18/19 | 3/4 | 3/4 | FAIL | 4/6 (64k) | 3/3 | ~163 | unsloth Q4_K_M A3B MoE ~17GB. Full 37-task 2026-07-03: 32/37, Skill L2 (web fastapi fail caps it; L4 coding-only). FAIL: hashmap (L5 capability gap), fastapi_endpoint, **para_entities (CONFIRMED genuine capability gap at ctx=32768, not a ctx-window issue — A3B MoE cannot do L5 game-state regardless of ctx; contrast gemma4:31b-qat which PASSES entities)**. ctx_128k TOOL_ERROR (KV exhaustion at 131072); 256k SKIPPED_CTX. |
| qwen3-30b:2507 | 2×24GB | — | — | — | — | 5/5 (128k) | 3/3 | 78.7 (ctx) | ctx_128k 43.8 tok/s, slower than 2026-07-22's 63.4 (different binary — ls10094 tensor_split overhead). 256k SKIPPED_CTX (arch limit 131072). multihop 77.7 avg. max_ctx=65536 (single GPU) / 131072 (2×24GB). Added to 24gb.txt + 2x24gb.txt. |
| qwen3-30b:deepseek | 1×24GB | spot 7/10 | — | — | FAIL | — | — | 185.9 | noctrex Qwen3-30B-A3B DeepSeek-Distill-2507 MXFP4, ~15.9GB, Ampere+. REJECTED (below 8/10). FAIL: csv_nordic (distillation regressed it — qwen3-30b:2507 base passes), hashmap (base gap), paratrooper. No reasoning spiral on expr_eval (PASS, 8.4s — distillation did not import DeepSeek's spiral bug). +14% speed vs 2507 base irrelevant given quality regression. Do not use. |
| qwen3-coder:30b-mxfp4 | 1×24GB | 18/19 | — | — | FAIL | — | — | 172 | Face314 MXFP4 A3B, ~15.9GB, Ampere+. Same Qwen3-Coder-30B-A3B arch as qwen3-coder:30b-1m; same hashmap capability gap. MXFP4 ~7% slower than Q4_K_M (172 vs 185) for ~1GB VRAM saving, no quality difference — **rule: for A3B MoE, Q4_K_M preferred over MXFP4 on RTX 4090** (confirmed again on Qwen3.5-35B, noctrex MXFP4 was 25% slower than bartowski Q4_K_M). Skill L4 coding. Added to 24gb.txt. |
| lfm2:8b | 1×24GB | spot 3/10 | — | — | — | — | — | 320.8 | Liquid AI MXFP4 A1B, ~4.5GB. Speed record (beats mellum2:12b's 254). Terrible quality: fails slugify, csv_nordic, csv_parser, expr_eval, hashmap, paratrooper; node_para_core NO_BLOCKS (format failure at L3). Not useful beyond L1. Do not add to any model set. |
| ernie4.5:21b | 1×24GB | spot 5/10 | — | — | — | — | — | 190 | Baidu/noctrex MXFP4 A3B, ~11.5GB. First Baidu model tested. Fails slugify, csv_nordic, csv_parser, hashmap. Cold-start 51s. Rejected. |
| Huihui-MoE-24B-A8B | 1×24GB | spot 4/10 | — | — | FAIL | — | — | 132.6 | mradermacher i1-Q4_K_M, ~13.9GB, no Ampere+ needed. REJECTED. FAIL: slugify (NO_BLOCKS, `<think>` block never exits — format pathology, same family as huihui-60b's bracket-wrapper), csv_nordic (capability gap), csv_parser (NO_BLOCKS TRUNCATED), hashmap (capability gap not format), node_para_core. A8B active does NOT beat A3B (qwen3-30b:2507 scores 8/10 at 181 tok/s with A3B) — architecture/training dominates active-param count. Do not retry. |
| Huihui-MoE-23B-A4B | 1×24GB | spot 6/10 | — | — | FAIL | — | — | 150.6 | mradermacher i1-Q4_K_M, ~13.3GB, no Ampere+ needed. REJECTED (below 8/10). PASS: safe_div, slugify, lru_cache, **csv_nordic**, tokenizer, node_para_core (format compliance clean through L3, unlike A8B sibling). FAIL: csv_parser (quick capability fail, clean format), expr_eval/hashmap/paratrooper (all NO_BLOCKS TRUNCATED — 8000-token think-loop pathology only above L3). A4B is an architectural improvement over A8B but still unusable above L3 at 8000-token budget; untested whether 16000+ fixes expr_eval (hashmap likely a capability gap regardless, per A8B's clean TESTS_STILL_FAIL on it). Token efficiency 0.078 p/k. |
| GroveMoE-Inst | 1×24GB | 0/10 | — | — | — | — | — | 124.7 | inclusionAI/noctrex MXFP4, ~17.1GB, Ampere+. REJECTED — inference corruption, not a capability failure: all 10 tasks emit `!!!` garbage (154k tokens, zero useful output). `grovemoe` arch not correctly supported by llama-server 10094. Needs a build with grovemoe support to retry. |
| Moonlight-16B-A3B | 1×24GB | spot 4/10 | — | — | FAIL | — | — | 175.7 (125-197 range) | Kimi/noctrex MXFP4 A3B, ~8.7GB, Ampere+. REJECTED. PASS: safe_div, lru_cache, tokenizer, node_para_core (same surprise pass as mellum2:12b — Kimi handles L3 game-state). FAIL: slugify (caps Skill L1), csv_nordic, csv_parser, expr_eval, hashmap. Same A3B ceiling as ernie4.5:21b/lfm2:8b; new arch family, no quality edge. Do not benchmark further. |
| granite4:small | 1×24GB | spot 7/10 | — | — | FAIL | — | — | 77.6 | IBM Granite 4.0 H-Small/noctrex MXFP4, ~18.5GB. Much slower than expected for MXFP4 (~110 est). Passes csv_parser+node_para_core; fails csv_nordic, hashmap. Below threshold. |
| qwen3-coder-reap:25b | 1×24GB | spot 7/10 | — | — | FAIL | — | — | 155 | noctrex MXFP4 A3B, ~13.1GB. REAP post-training; fails csv_nordic, hashmap, paratrooper. Inferior to qwen3-30b:2507 on quality and speed. Rejected. |
| qwen3-next:80b | 2×24GB, 3×24GB | 29/32 eligible | — | — | FAIL | 6/6 (incl. 256k on 3×24GB) | 3/3 | 109.3 (2×24GB full-run 2026-06-24) / 64.0 (2×24GB ctx, ls10094) | bartowski Q4_K_M ~45GB **DOES NOT FIT on 2×24GB** (cudaMalloc fails 23.9GB on device0, tensor_split=1\|1) — minimum tier 3×24GB, tensor_split=1\|1\|1. noctrex MXFP4 (~41GB) does fit on 48GB. Fails node_para_core, para_entities, paratrooper. Skill L2. context_256k OOM on 2×24GB (48GB) but CONFIRMED PASS on 3×24GB (72GB) at 37.7 tok/s — KV footprint smaller than estimated. max_ctx=262144 in 3x24gb.txt, 131072 in 2x24gb.txt. Abliterated=uncensored. |
| Qwen3-VL-235B-A22B Q3_K_M | 2×24GB (37GB resident + ~75GB DDR5) | spot (partial) | — | — | FAIL | — | — | 2.8 | unsloth 112GB, capability preview 2026-06-28, ngl=30→37, tensor_split=1\|1. **PASS python_hashmap (L5) — definitive at Q3, every <80B model tested fails this.** PASS node_para_core (where qwen3-next:80b, qwen2.5-coder:32b-q4 fail; quest:35b also passes — not a universal A3B gap). FAIL paratrooper (TESTS_STILL_FAIL at 1588s/3.8k tokens — correct constructor, wrong game loop, same universal wall; not a timeout). Clearly a higher tier than all <80B models on the two hardest discriminators, but still hits the universal L6-full wall. 72s startup. |
| qwopus3.6:35b | 1×24GB | 19/19 | 3/4 | 2/4→4/4‡ | FAIL | 5/6 (128k single-GPU) | 3/3 | 160.0 (full 37-task) / 161.8 (coding) | jashepp, Qwen3.6-35B-A3B coder fine-tune, MXFP4 Q8_0-Imatrix, ~19.8GB, Ampere+. Full 37-task 2026-07-22: Skill L4, fastest model with perfect coding at the time. Web FAIL: fastapi_endpoint (coder fine-tune breaks whitespace validation). Same base as noctrex-qwen3.6:35b (32/33) but jashepp's recipe runs +34% faster. ‡Single-GPU para_entities: GPU froze during prefill at ctx=32768 (VRAM exhaustion, 0 tok/s/3600s) — RESOLVED at 2×24GB: 4/4 PASS at 122.7 avg (tensor_split frees VRAM headroom). agents-a1:35b (same jashepp family, different base): FAIL csv_nordic, 7/10, 159.8 tok/s, Skill L2 — rejected; qwopus3.6's Qwen3.6-35B-A3B base explains the quality gap. |
| qwopus3.6:35b | 2×24GB | — | — | 4/4 | FAIL | 5/6 (128k) | 3/3 | 77.4 (ctx, ls10094) / 83.8 (multihop) | f16 KV. 4090 spikes to 350W TDP. max_ctx=32768 (1GPU) / 131072 (2×24GB). ctx_64k dropped from prior-binary 114.7→81.7 tok/s on ls10094 (-29%, consistent binary overhead for MXFP4 MoE). Added to 24gb.txt + 2x24gb.txt. |
| equinox:31b | 1×24GB | 19/19 | 4/4 | 3/4 | FAIL | 32k hard cap (1GPU) | 3/3 | 35.5 | jashepp dense 31B MXFP4 Q8_0-Imatrix, ~16.4GB, Ampere+. Full 37-task 2026-07-04: 32/37, Skill L4. **Only single-24GB model confirmed with 19/19 coding + 4/4 web simultaneously** (original basis for the "dense ≥31B" fastapi cutoff rule, later revised — see fastapi discriminator notes below). FAIL: **para_entities (CONFIRMED genuine capability gap at ctx=32768 on 2×24GB, NOT a ctx-window artifact — generates a full wrong-logic implementation, not NO_BLOCKS)**, paratrooper. PASSES combat only because the step-4 scaffold supplies a reference entities impl. f16 KV (weights ~16.4GB + f16 KV at 64k ≈27.4GB > 24GB, hence 32k single-GPU cap). |
| equinox:31b | 2×24GB | — | — | — | — | 5/5 (128k) | 3/3 | 23.1 (ctx) / 22.6 (multihop) | python_hashmap PASS at 37.8 tok/s (no q8_0-style regression at tensor_split=1\|1, f16 KV maintained). Slower than 2026-07-22 binary (31.1/27.3 at 64k/128k) — ls10094 overhead on dense MXFP4 31B context. max_ctx=131072. |
| gemma4:31b-qat | 1×24GB | 18/19 | 4/4 | 3/4→4/4(2×24GB) | FAIL | 32k (1GPU) | — | 42.3 (coding) / 42.2 (web) | lmstudio-community dense 31B QAT Q4_0, ~16.4GB, no Ampere+ needed. Full 2026-07-24/25: 31/37, Skill L4. QAT (quantization-aware training) strictly better than PTQ Q4_K_M at same bit rate. **PASS csv_nordic (dense arch fixes the Gemma4 A4B MoE structural gap), dijkstra+hashmap (QAT int4 preserves L5 precision at f16 KV)**. Web 4/4 PERFECT incl. fastapi — the "dense ≥31B" fastapi rule originally rested on this + equinox:31b, later revised (QAT A4B 26B also passes, see below). |
| gemma4:31b-qat | 2×24GB | — | — | 4/4 | FAIL | 5/5 (128k) | 3/3 | 23.7 (ctx) / 23.4 (multihop) / 32.5 (L6-stepped) | **L6-stepped 4/4 PASS confirmed — completes the full stepped chain** (core/turret/entities/combat), unlike equinox:31b at the same 31B-dense tier which FAILS entities — QAT training format + Gemma4 architecture, not just "dense 31B", determine L5 game-state capability. paratrooper TESTS_STILL_FAIL (constructor PASS, game loop wrong — universal wall holds). Same ~40-43 tok/s speed tier as equinox:31b. f16 KV, max_ctx=32768(1GPU)/131072(2×24GB). Added to both. |
| qwen3-48b:a4b | 1×24GB | spot 4/10 | — | — | — | — | — | 145→13.2 (collapses under ctx) | DavidAU Qwen3-48B-A4B 12-expert distill, Q4_K_M, ~19GB. REJECTED. node_slugify FAIL caps Skill L1. csv_nordic TOOL_ERROR — server froze during prefill at ctx=32768 (VRAM exhaustion, same kernel-stall class as qwopus3.6:35b's entities hang). Severe KV thrash (145→35→13.2 tok/s as ctx/generation grows). 12-expert distill merge degrades quality. Do not retry. |
| huihui-60b | 2×24GB | spot 4/10 | — | — | — | — | — | 154.4 | noctrex Huihui-MoE-60B-A3B MXFP4, 2-part ~30.3GB, Ampere+. REJECTED. node_slugify NO_BLOCKS — wraps output in `[thinking: BEGIN_FILE ...]`, parser never finds standalone BEGIN_FILE (format pathology). Even if fixed, remaining A3B ceiling failures (csv_nordic, csv_parser, tokenizer, hashmap, paratrooper) cap at 5/10. Same A3B pattern as qwen3-30b:2507/ornith:35b family. Do not retry. |
| laguna-s-2.1:118b (IQ3_XXS) | 2×24GB | 17/19 | — | — | — | — | — | 96.1 | Poolside 118B MoE A8B, wimmmm IQ3_XXS, ~42.1GB. Full 19-task coding 2026-07-27: Skill L3. ~8B active/token, largest A8B tested. FAIL: csv_nordic (TESTS_STILL_FAIL, 68s, wrong solution — later CORRECTED, see IQ4_XS row: this IS a precision gap not structural), csv_parser (quoted-comma, structural, unchanged by quant). PASS incl. **hashmap (L5 precision preserved at 3-bit!)**. python_dijkstra anomaly 38.3 tok/s under KV pressure. IQ4_XS (58.4GB) OOMs on 2×24GB (29.2GB/GPU). |
| laguna-s-2.1:118b-iq4 (IQ4_XS) | 3×24GB | 18/19 | 4/4 | 4/4 | — | 3/3 (8k-32k)+3 SKIPPED (64k+) | 3/3 | 54.3 (coding) / 56.4 (web) | tensor_split=1\|1\|1, ./gpu-mode.sh multi + --model-timeout 1200. **csv_nordic flips to PASS at IQ4_XS** (vs FAIL at IQ3_XXS) — CORRECTS the prior assessment: this is a precision gap, not structural; csv_parser still FAILS at IQ4_XS too (structural, unchanged by quant tier). L6-stepped CONFIRMED 2026-08-13 4/4 — **key finding: A8B active params clear the para_entities wall that blocks all A3B models**. Context 3/3 PASS 8k-32k, 64k+ SKIPPED_CTX (max_ctx=32768 task default). Multihop 3/3. Full profile: 18/19 coding+4/4 web+4/4 L6-stepped+3/3 ctx(8k-32k)+3/3 multihop. |
| qwen3-coder-rtpurbo:30b | 1×24GB | 18/19 | 2/4 | — | — | — | — | 211.4 (coding, speed record at this quality tier) | mradermacher Qwen3-Coder-30B-A3B RTPurbo, i1-Q4_K_M, ~17.3GB, no Ampere+ needed. **csv_nordic + csv_parser PASS (base qwen3-coder:30b-1m fails both — RTPurbo post-training fixed them)**. FAIL: hashmap (base Qwen3-Coder gap, shared by all variants). Web FAIL: config_loader (partial-method-completion, same gap as 1m), fastapi (A3B coder pattern — Field(min_length=1)). 31% faster than qwopus3.6:35b (161.8, 19/19). Token efficiency 2.308 p/k. Added to 24gb.txt. (Same-scout GLM-4.7-Flash-REAP: 6/10 REJECTED — REAP regressed both csv_nordic+csv_parser vs base glm4.7-flash.) |
| gpt-oss:120b | 3×24GB | 19/19 | 4/4 | 4/4 | FAIL (1st wall-breaker was qwen3.8:27b, see below) | 5/5 (128k; 256k SKIPPED_CTX, arch limit 131072) | 3/3 | 56.1 (coding, ls10094) / ~55 (full run) | OpenAI MXFP4 single-file ~60GB, ggml-org, 3×24GB required, tensor_split=1\|1\|1. Full 37-task 2026-08-11: 32/34 eligible, Skill L6. **First model with PERFECT 19/19 coding + PERFECT 4/4 web simultaneously, and first to complete the full L6-stepped chain.** csv_nordic 10.4 tok/s (thinking+large prefill); others 20-76. thinking=true confirmed working, no planning loops at 3×24GB. On single 24GB needs n_cpu_moe=35 CPU offload (~17 tok/s RAM-bound); fully GPU-resident at 3×24GB. max_ctx=131072 (q8_0 KV GQA footprint smaller than estimated — fits comfortably at 72GB split 3 ways). GPU max 66°C. |
| qwen3.5-122b:a10b | 3×24GB | 19/19 | 4/4 | 4/4 | FAIL | 5/5 (128k; 256k OOM, VRAM ceiling) | 3/3 | 37.4 (coding) | jamiefutch Qwen3.5-122B-A10B MXFP4 MTP-merged, ~65.1GB, 3×24GB required, Ampere+, q8_0 KV. **A10B active params break both A3B ceilings**: hashmap PASS 29.0 tok/s, node_para_core PASS 18.9 (both fail for most A3B MoE). java_word_freq PASS (gemma4:26b-qat otherwise 18/19 fails this specific task). csv_nordic PASS 16.1 tok/s (thinking+prefill, like gpt-oss:120b). No expr_eval spiral (unlike deepseek-r1:32b). **MTP head merged into single GGUF — zero speed penalty** (unlike carnice:35b-mtp's separate-head 4-5× penalty). 37.4 avg slower than gpt-oss:120b's ~55 — A10B more compute-heavy than gpt-oss MoE (consistent with A3B→A10B 3.3× active-param scaling). context_256k OOM (65.1GB weights leave ~6.9GB/GPU KV; 131072 fits, 262144 doesn't). Requires ./gpu-mode.sh multi + --model-timeout 1200. |
| qwen3.8:27b | 1×24GB | 19/19 | 4/4 | 4/4 | **PASS — first ever**, file-specific outlier (see below) | 256k (2×24GB only; 1GPU drops to ~10 tok/s past 64k) | 5/5 | 44.9 (coding) / 45.5 (web) / 45.6 (L6-stepped) | unsloth Q4_K_M, ~18.4GB, no Ampere+ needed, thinking=true, **f16 KV required** (q8_0 causes hashmap `_EMPTY` omission — same rule as qwen3.6:27b). **NEW Gated DeltaNet hybrid**: 64 layers = 16 Gated-Attention + 48 DeltaNet (linear recurrent); only 16/64 accumulate KV → ~16KB/token vs ~128KB/token standard dense (≈2.1GB total KV even at max_ctx=131072). Requires llama-server ≥2026-08-13 (qwen35.cpp merge, commit 27df9199d+; now pinned to **67a17c17c**, see rebuild history below). See the dedicated node_paratrooper investigation paragraph immediately below this table for the full cross-GPU root-cause story (PASS single-GPU, FAILS at explicit tensor_split=1\|1 on 2×24GB, PASSES again at 3×24GB — floating-point reduction-order non-determinism, confirmed via byte-diff of generated code) and the later file-specificity finding (of 6 independently-quantized builds × 3 GPU configs, only this exact original GGUF ever passes on both single-GPU and 3-GPU; see "qwen3.8:27b rebuild/outlier" in Extended Model Investigations and `models/candidates.txt` for the regression history across later llama.cpp commits). ctx_128k single-GPU is SLOW (10.2 tok/s, not the ~34 tok/s the 8k-64k trend predicts) but this is a general single-GPU-VRAM-saturation pattern, not DeltaNet-specific — dense qwen3.6:27b is even slower (4.6 tok/s) at the same depth on the same hardware. 2×24GB (3-GPU auto-dist, no tensor_split): context_256k PASS 19.0 tok/s/358.4s, 4× faster wall-clock than the single-GPU 128k run despite 2× the tokens. 27/27 PASS (19 coding+4 web+4 L6-stepped) confirmed unaffected by the paratrooper config-sensitivity at tensor_split=1\|1. Added to 24gb.txt + 2x24gb.txt. |
| qwen3.5:27b | 2×24GB | 19/19 | 4/4 | 4/4 | FAIL | 6/6 (256k) | 3/3 | 28.4 (coding) | bartowski dense Q4_K_M, ~16GB, thinking=true, q8_0 KV. CONFIRMED 2026-08-13 complete profile — **Skill L6, every task group perfect except paratrooper**. Web 4/4 incl. fastapi — **first dense 27B to pass fastapi, BREAKS the "dense ≥31B" cutoff; revised rule: all dense models pass fastapi regardless of size**. L6-stepped 4/4 incl. entities — **dense 27B passes where A3B MoE of the same generation (qwen3.5:35b) fails, confirming the entities gap is MoE-architectural, not generational**. Dramatically faster than qwen3.6:27b at ctx=32768 (~28 vs ~12 tok/s) — q8_0 KV (NOT f16; the f16 rule applies only to qwen3.6:27b/qwen3.8:27b) gives 2× memory efficiency here while still preserving hashmap precision. max_ctx=131072. GPU max 65-69°C. |
| **python_fastapi_endpoint web-group cross-model table** (various configs, 2026-07-02 through 2026-08-13) | — | — | — | — | — | — | — | — | qwen3.5-122b:a10b 4/4@38.4; qwen3.5:27b 4/4@27.8 (breaks dense≥31B); qwen3.6:35b-A3B unsloth 4/4@101.1 (same base as noctrex, confirms Qwen3.6-A3B instruct passes regardless of quant format); noctrex-qwen3.6:35b 4/4@116.7; equinox:31b 4/4@40.3; qwen2.5-coder:32b-q4 4/4@33.3; gemma4:31b-qat 4/4@42.2 (confirms dense≥31B is architectural, not Qwen-specific); **gemma4:26b-qat 4/4@126.6 — BREAKS dense≥31B, first MoE and first sub-31B model to pass, QAT Q4_0 is the likely differentiator**; qwen3-coder:30b-1m 2/4@150.8 (FAIL config_loader+fastapi, partial-method-completion); quest:35b 2/4@131.2(ollama)/107.5(ls10094) (FAIL config_loader+fastapi, RL fine-tune A3B); glm4.7-flash 3/4@112.8 (FAIL fastapi, Field(min_length=1) accepts "   " as valid); qwen3-30b:2507 3/4@162.1 (same FAIL pattern); qwopus3.6:35b 3/4@161.8 (FAIL fastapi despite sharing noctrex's passing base — fine-tune-dependent, not architecture); qwen3-coder-rtpurbo:30b 2/4@192.9 (same 2-task FAIL as 1m); qwen3.5:35b 3/4@119.4 (FAIL fastapi, PASS the other 3). **Revised discriminator (2026-08-13): dense passes regardless of size; MoE passes only when standard-instruction or QAT; post-trained MoE (coder/RL/agentic) uniformly fails; thinking doesn't help MoE.** Second discriminator, python_config_loader: fails models with Python *structural* gaps (qwen3-coder:30b-1m, quest:35b — both also fail python_multifile_rename). |
| north-mini-code | 1×24GB | spot 6/10 | — | — | — | — | FAIL (distractor) | 141 | Cohere 30B MoE 3B active, Q4_K_M, ~18GB. Format non-compliant on complex tasks — agentic training emits verbose prose/markdown before code, exhausting 8000-token budget before BEGIN_FILE on csv_nordic, tokenizer, node_para_core (all NO_BLOCKS). Token efficiency 0.130 p/k (worst seen). Passes hashmap where format compliance holds. distractor_notes TESTS_STILL_FAIL (wrong retrieval). Do not benchmark further without a format fix. |
| gemma4:26b | 1×24GB | spot 7/10 | — | — | FAIL | — | — | 124.4 | noctrex Gemma4 A4B MXFP4, ~15.4GB, Ampere+. SKIP (below 8/10). PASS incl. **hashmap (L5! — first confirmed Gemma4 A4B pass on this canary)**, node_para_core. FAIL: csv_nordic (wrong solution at ~2.6k tokens), csv_parser (TRUNCATED — 16k budget consumed by verbose preamble, structural, not fixable by more budget). hashmap PASS distinguishes this from stronger-looking rejects (glm4-tulu:32b, glm4.7-flash) that also fail it. |
| gemma4:26b-qat | 1×24GB | 18/19 | 4/4 | 3/4(1GPU)→4/4(2×24GB) | FAIL | 6/6 (256k, 2×24GB) | PASS | 129.3 (coding) / 126.6 (web) | lmstudio-community Gemma4 A4B QAT Q4_0, ~13.4GB, no Ampere+ needed. Spot 9/10→promoted→18/19 full coding. FAIL: java_word_freq only (4.38s quick capability fail). **BREAKS "dense ≥31B" fastapi cutoff — first non-dense-≥31B pass; QAT Q4_0 is the likely key, not active-param count.** QAT vs MXFP4 (same arch, different quant) comparison: csv_nordic FAIL→PASS, csv_parser TRUNCATED→PASS, fastapi untested→PASS — **QAT eliminates the verbose-preamble pathology entirely and fixes both CSV capability and fastapi validation**. L6-stepped single-GPU 3/4 (entities NO_BLOCKS — ctx=8192 default, a window issue not capability) → 2×24GB --num-ctx 32768: 4/4 PASS. Effective Skill L3 (java_word_freq caps; hashmap+dijkstra PASS). context_256k PASS at same speed tier as 128k (62.4 vs 62.7 tok/s) — architecture handles 262144 cleanly at only 13.4GB weights. Added to 2x24gb.txt. |
| glm4-tulu:32b | 1×24GB | spot 6/10 | — | — | FAIL | — | — | 40.6 | mradermacher ZhipuAI GLM-4-32B dense, Tulu i1-Q4_K_M, ~19.7GB. SKIP. FAIL: csv_nordic, **hashmap (dense GLM-4-32B does not pass the canary; Tulu fine-tune makes no difference)**, node_para_core. Dominated by glm4.7-flash (29/33 @111 tok/s) despite being 4GB larger. Same ~41 tok/s speed tier as qwen2.5-coder:32b-q4/equinox:31b but worse quality than both. Rejected. |
| quest:35b | 2×24GB (3-GPU auto / tensor_split=1\|1) | 17/19 | 2/4 | 4/4 | FAIL | 6/6 (256k) | 3/3 | 100.0 (coding, ls10094) / 97.3 (tensor_split=1\|1 spot) | Almost certainly Qwen3.6-A3B base (entities PASS = strong Qwen3.6 discriminator). **llama-server 10094 kq-mask regression swapped two failures vs ollama: python_multifile_rename FAIL(ollama)→PASS(ls10094); python_hashmap PASS(ollama)→FAIL(ls10094)**. Web FAIL: config_loader+fastapi (RL fine-tune A3B pattern, matches ollama result). L6-stepped 4/4 (11th completer), very slow at 3-GPU auto-dist (no tensor_split in config: core 24.9→combat 10.5 tok/s, needs --model-timeout 600) vs 97.3 tok/s once tensor_split=1\|1 is set (now fixed in 2x24gb.txt). context_256k 52.4 tok/s — 3× faster than qwen3.5:27b dense (16.4) at same ctx (MoE A3B efficiency). **⚠ UPDATE 2026-09-26: on the current pinned 67a17c17c binary, python_hashmap is itself GPU-split-dependent for this model — 3/3 PASS single-GPU, 3/3 FAIL at 2×24GB tensor_split=1\|1 (confirmed via the cross-GPU sensitivity sweep below) — the "17/19"/FAIL-hashmap figure above was measured on ls10094; on 67a17c17c this task's result depends on which GPU split is used. Treat any single-config hashmap result for this model as provisional.** |
| qwen3.6:35b-A3B (unsloth UD-Q4_K_M) | 2×24GB | 17/19 | 4/4 | 4/4 | — | 6/6 (256k) | 3/3 | 99.7 (coding) / 71.0 (ctx) / 97.4 (L6-stepped) / 86.7 (multihop) | thinking=true, f16 KV. FAIL: csv_nordic (kq-mask regression, same as noctrex variant), csv_parser (quoted-comma structural gap — noctrex's MXFP4 build passes this, Q4_K_M at ls10094 does not). PASS hashmap (f16 KV correct for this arch), dijkstra. Web 4/4 confirms Qwen3.6-A3B base instruction model passes fastapi (no coder/RL penalty). Full profile Skill L6 (17/19+4/4+4/4+6/6+3/3). |
| qwen3.5:35b | 2×24GB | 3/4 (web only shown) | 3/4 | FAIL (entities) | FAIL | 6/6 (256k) | 3/3 | 77.2 (ctx) / 93.4 (multihop) | A3B MoE Qwen3.5 generation. **FAILS para_entities (CONFIRMED genuine capability gap at ctx=32768/num-predict=16000, TESTS_STILL_FAIL 103.4 tok/s — not a ctx-window issue)**; core/turret/combat PASS. Web FAIL fastapi only (3/4). context_256k 55.7 tok/s — between noctrex Qwen3.6 (46.1) and quest:35b (52.4). Key architectural finding alongside qwen3.5:27b: **the entities gap is A3B-MoE-specific, not a Qwen3.5-generation issue** — dense Qwen3.5:27b passes entities, A3B Qwen3.5:35b fails it. |
| noctrex-qwen3.6:35b | 2×24GB | 32/33 (full-run 2026-06-24)→34/37‡ | 4/4 | 4/4 | FAIL | 6/6 (256k) | 3/3 | 121 (2026-06-24 full run) / 68.0 (ctx, ls10094) | MXFP4 MoE. L6-stepped 4/4 (the 2026-07-23 single-GPU entities FAIL was a ctx=8192 window issue, resolved at --num-ctx 32768 on 2×24GB). Web 4/4 incl. fastapi (field_validator+.strip()). ‡REGRESSION 2026-07-23 (ls10094 kq-mask #25370): csv_nordic UNEXPECTED FAIL (was PASS 2026-06-24/07-03) — regression confirmed stable across later binaries too (still FAILS as of the 2026-08-15 binary-regression spot-check). context_256k 46.1 tok/s (ls10094) vs prior-binary 75 tok/s — consistent binary overhead pattern. No `thinking` flag set for this MXFP4 config. |
| qwen3.6:27b | 2×24GB (3-GPU auto, f16 KV) | 35/37 | — | 4/4 | FAIL | 4/6 (64k; 128k NO_BLOCKS slow-but-passes control, 256k SKIPPED/TOOL_ERROR history) | — | 43.9 (2026-07-23 compare) / 40.2 (2026-06-24) | Dense 27B, f16 KV required (hashmap precision rule). 2026-07-23 compare: 35/37, Skill L5; context_256k TOOL_ERROR 7200s (max_ctx cap now fixed in default.txt). L6-stepped 4/4 CONFIRMED at --num-ctx 32768 (very slow: core 13.4→combat 9.6 tok/s over 417s, needs --model-timeout 600 — dense attention at 32k ctx is O(n) bandwidth-bound, ~3.75GB KV causes 3×+ slowdown vs 8k). Served as the DENSE-27B ctx_128k control for qwen3.8:27b's DeltaNet investigation: 4.6 tok/s/2275.9s — actually *worse* than qwen3.8:27b's 10.2 tok/s at the same depth, proving the single-GPU slowdown past 64k is a general VRAM-saturation pattern, not DeltaNet-specific. Binary-regression spot-check (2026-08-15, same build as qwen3.8:27b): hashmap PASS 44.4 tok/s, no drift. Also confirmed to also FAIL paratrooper on single-GPU (not just its documented 3-GPU auto-dist config) — a genuine large capability gap, not qwen3.8:27b-style config sensitivity. |
| **2×24GB full-run compare, 2026-06-24** | — | — | — | — | — | — | — | — | qwen3.6:27b 32/33@40.2, noctrex-qwen3.6:35b 32/33@121 — both fail only paratrooper (universal wall). quest:35b 29/33@131.8, Skill L1 (python_multifile_rename fails on this older ollama binary — later reversed on ls10094). context_256k: qwen3.6:27b 26 (prior binary), noctrex 75, quest:35b 73. |
| **2026-07-23 default.txt single-GPU compare** (llama-server 10094, 8/9 models run, gpt-oss:120b skipped — GGUF not downloaded) | — | — | — | — | — | — | — | — | qwen3.6:27b 35/37@43.9 Skill L5; noctrex-qwen3.6:35b 34/37@140.9 L2 (csv_nordic UNEXPECTED FAIL regression); qwen3.5:35b 33/37@159.9 L2; equinox:31b 32/37@40.5 L4; qwen3-30b:2507 31/37@177.3 L2; glm4.7-flash 31/37@131.8 L1 (config_loader UNEXPECTED FAIL regression); qwen2.5-coder:14b 27/37@83.2 L2; gpt-oss:20b 25/37@227.8 <L1 (9 NO_BLOCKS — non-deterministic model, see below). **Cross-pattern: each model regressed on a DIFFERENT task (noctrex→csv_nordic, glm4.7-flash→config_loader), ruling out task-level flakiness — the ls10094 kq-mask f16 change (#25370) shifted attention model-architecture-specifically, not fixable without a new binary or bisect.** Prior-binary scores: noctrex 34/37→35/37, glm4.7-flash 31/37→32/37. |
| gpt-oss:20b | 1×24GB | varies 22-26/33 | — | — | — | 4/6 (stable fail at 64k) | 2/3 | 227.8 | **Non-deterministic at temperature=0** — verbose "semi-thinking" in plain-text output (not reasoning_content) has variable length between identical runs (22/33 to 26/33 observed), exhausting the 4800-8000 budget inconsistently on python_minheap/dijkstra/hashmap/tokenizer/para_combat. Needs 8000+ for expr_eval/tokenizer. Stable failure: context_64k TESTS_STILL_FAIL (wrong retrieval, RC-5000 instead of correct value — a retrieval bug specific to that depth, not budget). Skill <L1. Adding `thinking` does NOT help (different planning loop) — correctly left without it. Consider excluding from the canonical comparison set given the non-determinism. |
| gpt-oss-120b Fable-5 (Q5_0, 75.1GB) | 3×24GB | — | — | — | FAIL | — | — | 7.8-9.2 | CONFIRMED REJECTED 2026-08-12. 6-7× slower than GPU-resident base gpt-oss:120b (55 tok/s). Fable-5 distillation does not fix the L6 universal wall (paratrooper still fails). See `candidates.txt` for full results. |
| qwen3.8-flash-next (official unsloth UD-Q4_K_XL, ~106GB 4-part) | 3×24GB via --fit | — | — | node_para_core FAILS 6/6 | **PASS on 67a17c17c, 2nd confirmed ever** (2026-09-03, 6/6 repeat-verified); **FAILS 3/3 deterministically on bed0a8566, see Notes** | **6/6 incl. 256k, CONFIRMED on production 67a17c17c** (128k: 12.2 tok/s/703.4s; 256k: 11.3 tok/s/1365.1s — re-verified 2026-10-03, replacing the earlier bed0a8566-only numbers) | — | ~22-24 (183-244s per run, 67a17c17c) | qwen4exp architecture (Gated DeltaNet + QSA hybrid + N-gram Embedding + MTP), needs mainline llama.cpp ≥ the qwen4exp merge (now pinned 67a17c17c). Unlike qwen3.8:27b's pass this is NOT tied to one irreplaceable file — standard rebuildable unsloth quant + standard binary. **Does NOT complete the full L6-stepped chain** (node_para_core step-1 fails reliably) — a from-scratch paratrooper pass in isolation, a genuinely different achievement from the stepped-chain completers. `--fit on --fit-target 4096` only (never combine with `-ngl`/`--tensor-split`, they conflict with --fit's auto-placement and cause OOM fallback). Context_128k/256k are notably slower (12.2/11.3 tok/s) than this model's short-task baseline (~22-24 tok/s) — long-context decode is genuinely slower here on this architecture at this VRAM tier, a real number not an artifact (⚠ this specific re-verification run was invoked via bare `bench.py`, not `./run.sh`, so hwmonitor did NOT cover it — see the bench.py/hwmonitor gap note in Known Issues; no crash occurred and pre/post snapshots were normal, but treat as unmonitored, not as a clean pass on that front). **THIRD REGRESSION CONFIRMED 2026-10-03 at commit `bed0a8566`** (608 commits past the pin, included the qwen4exp MTP/tensor-split/GDN-fix cluster that motivated the attempt — see Extended Model Investigations below): python_hashmap 23.0→8.16 tok/s (−64.5%), python_expr_eval 23.2→6.38 tok/s (−72.5%), python_safe_div ~19-24→30.47 tok/s (faster, same short-task-spared pattern as both priors). **Worse than a speed regression this time: node_paratrooper FAILS 3/3, deterministically (identical eval_count=5311 every run)** — the first of the three rebuild attempts to actually lose a confirmed capability, not just slow it down. Reverted back to the `67a17c17c` pin same day. **SPEED REGRESSION ROOT-CAUSED 2026-10-03 via `git bisect`: commit `c61b98b875` ("model: add NVIDIA Nemotron-3-Puzzle-75B-A9B support", #25444)** — changed `build_moe_ffn`'s per-decode-step expert-aggregation loop in `src/llama-graph.cpp` from reading `hparams.n_expert_used` (a plain scalar field) to calling `hparams.n_expert_used(il)` (a per-layer accessor function), to support Nemotron-3-Puzzle's heterogeneous per-layer expert counts. For qwen4exp (uniform expert count, no per-layer variation) this is value-equivalent but not performance-equivalent — 5/5 bisection steps in the `67a17c17c`(good)→`49c0dc82b`(bad) range came back bad, confirmed to sit at commit-graph position 1 of 35 (not the "82 commits" figure used elsewhere in this doc — that number was computed differently and is off; real `git rev-list --count` distance is 35). Mechanism confirmed via direct diff inspection, not just bisection — see `next-runs.md` for the full trail. **This explains the speed regression common to all three rebuild attempts (49c0dc82b, d81aef199, bed0a8566) — it's one bug, present from very early past the pin, not three unrelated issues.** The separate node_paratrooper capability loss (only present at bed0a8566, not at d81aef199) is a DIFFERENT, later-introduced regression — NOT bisected (Phase 2, ~213-commit range, was not attempted; Phase 1 alone took ~4 hours). Full rebuild/regression history (now reaffirmed a third time, after 49c0dc82b, d81aef199, and bed0a8566) in Extended Model Investigations below and `next-runs.md`. |
| qwen3.8-flash-next-16gb (same file/commit) | 1×16GB + CPU/NVMe expert paging | 18/19 | 4/4 | 4/4 | **PASS, 2/2** | 5/5 (128k; 256k SKIPPED_VRAM, min_vram_gb=48 guard) | 5/5 | 18.1 avg | RTX 5060 Ti 16GB + 88GB WSL RAM, CONFIRMED 2026-09-14/15, 37/38 eligible. Unlike the 3×24GB config above, **node_para_core PASSES here (2/2) and the full L6-stepped chain completes** — probably the different numerics of a 1-GPU+CPU-experts split vs. 3-GPU --fit (same class of effect as qwen3.8:27b's tensor_split sensitivity) rather than a capability difference. Only csv_parser fails (same format gap as the 3×24GB build). Recipe: `--fit on --fit-target 512 --no-repack` (never `--no-mmap`/`--mlock`), move model files off `/mnt/c` (WSL 9p, ~190MB/s) onto WSL ext4 first. |
| qwen3.8-flash-next-24gb (same recipe, one tier up) | 1×24GB + CPU expert offload | spot 8/10 | — | — | **PASS** | — | — | 16.7 avg | CONFIRMED 2026-09-26. **Slower than the 16GB box (16.7 vs 18.4 tok/s) despite 50% more VRAM** — contradicts the "more VRAM → faster" hypothesis this test was designed to check. node_para_core FAILS here (matches the 3×24GB rig, not the 16GB box) while paratrooper still PASSES — a 3rd independent VRAM tier to pass this task with this recipe, reasonably reproducible unlike qwen3.8:27b's file-specific pass. csv_parser fails as usual. |
| ornith:1.5-35b (jashepp, MXFP4 Q8_0-Imatrix) | 1×24GB | — | — | 4/4 | 1 PASS / 6 attempts (not reproducible) | — | — | ~155 | CONFIRMED 2026-08-24, 14th L6-stepped completer. entities PASS suggests Qwen3.6-A3B base, same lineage as qwopus3.6:35b. Unlike qwen3.8:27b/ornith:1.0-35b, paratrooper here is NOT reliably reproducible (1/6) — treat as a one-off, not a confirmed capability. Full entry in `candidates.txt`. |
| ornith:1.5-9b (jashepp, MXFP4 Q8_0-Imatrix, ~8.9GB) | 1×24GB | 17/19 | 3/4 | 3/4 | untested | 32k (hard cap, 3/3 within) | 3/5 | 79.3 (coding) / ~88 (web+L6+ctx) | CONFIRMED 2026-08-28 coding; web/L6/context/multihop CONFIRMED 2026-10-03. Fastest confirmed model in the 16GB/12GB tiers by a wide margin. FAILS csv_nordic_property + python_lfu_cache (both L3). PASSES node_csv_parser (L3) + python_hashmap (L5, strong for 9B-class). **Lineage clarified 2026-10-03: FAILS node_para_entities (TESTS_STILL_FAIL)** — the Qwen3.5-A3B-lineage signature, NOT Qwen3.6-A3B like the rest of the ornith family (ornith:1.0-35b, ornith:1.5-35b both PASS entities); core/turret/combat PASS (combat via step-4 reference scaffold). Web: FAILS python_fastapi_endpoint (TESTS_STILL_FAIL) — consistent with the A3B-MoE-fails/dense-passes fastapi pattern. Context: 3/3 PASS within the model's own max_ctx=32768 cap (8k/16k/32k); 64k+ SKIPPED_CTX as expected, not a capability gap. Multihop: 3/5 — PASS forward/reverse/distractor, FAILS multihop_chain_5 + multihop_cross_5 (both fast fails, not timeouts). Requires Ampere+ (MXFP4). f16 KV. hwmonitor WARN (GPU0 ~99-101% of 260W cap, routine, no CRIT). |
| **ornith:1.0-35b** (ornith-ai, Q4_K_M, ~21GB, no Ampere+) | 1×24GB | 18/19‡ | 3/4 | 4/4 | **PASS, 3/3 MD5-identical — 3rd ever, 2nd model (after qwen3.8:27b) to also complete the full L6-stepped chain, at ~3× its speed** | 3/3 (conservative 32k cap, see 2×24GB row) | 5/5 | ~131 (coding) | CONFIRMED 2026-09-25. Standard GGUF, no pinned commit, no irreplaceable file, no exotic quant — unlike both prior paratrooper passes. Web 3/4 (FAILS config_loader, NO_BLOCKS). ‡**Corrected from an original 8/10 spot-check** — see 2×24GB row; a 3×3 repeat matrix found python_hashmap reliably FAILS single-GPU (3/3) and csv_nordic_property's original single-GPU FAIL was a one-off anomaly (CLOSED 2026-09-26: replayed the exact original request sequence, ruled out session-state; 9/9 passes since, no trigger found). Real single-GPU score: 18/19 (hashmap only). Multi-GPU re-verification CONFIRMED 2026-09-25: 2-GPU explicit tensor_split=1\|1 FAILS paratrooper (149.3 tok/s/35.7s); 3-GPU explicit tensor_split=1\|1\|1 PASSES (13.0 tok/s/343.9s, much slower) — **the qwen3.8:27b cross-GPU fragility precedent holds exactly on a 2nd independent model**, confirmed via code diff (genuinely different, not just differently-flagged, generated code at each config). Use single-GPU to reliably reproduce the L6-full pass. Config variants (`-2gpu`,`-3gpu`) kept in `candidates.txt`. Added to `models/24gb.txt`. |
| ornith:1.0-35b | 2×24GB (tensor_split=1\|1, max_ctx=262144) | **19/19 (verified)** | — | 4/4 | FAIL (see single-GPU row) | **6/6 incl. 256k** (76.6 tok/s/132.1s) | 5/5 | 152.8 (coding/web/L6, 27/27 PASS) / 102.0 (ctx+multihop) | CONFIRMED 2026-09-26. **python_hashmap is a genuine, reliable cross-GPU flip — 3/3 FAIL single-GPU, 3/3 PASS here** — opposite direction from node_paratrooper's usual PASS(1GPU)→FAIL(2GPU) pattern, same underlying floating-point reduction-order mechanism. The single-GPU max_ctx=32768 cap was just conservative, not the real ceiling — matches other 35B-class MoE at this VRAM tier. |

**L6-stepped chain completers** (4/4 PASS on node_para_core/turret/entities/combat), by config: 3×24GB — gpt-oss:120b (~55 tok/s), qwen3.5-122b:a10b (~17 tok/s), laguna-s-2.1:118b-iq4 (~21 tok/s). 2×24GB (`--num-ctx 32768`) — noctrex-qwen3.6:35b (~91), qwen3.6:35b-A3B unsloth (~97), qwopus3.6:35b (~123), gemma4:26b-qat (~82), gemma4:31b-qat (~32), qwen3.6:27b (~12, f16 KV, needs `--model-timeout 600` for combat), qwen3.5:27b (~27, q8_0 KV — 10th completer, confirms the entities gap is A3B-MoE-specific not generational), quest:35b (~97 with tensor_split=1\|1; `--model-timeout 600` for combat). 1×24GB default ctx (compact MoE, no `--num-ctx` override needed) — glm4.7-flash (~111). 1×24GB `--num-ctx 32768` — ornith:1.5-35b (~155, 14th), ornith:1.0-35b (~131, 15th, **also passes L6-full**). 1×16GB + CPU/NVMe paging — qwen3.8-flash-next-16gb (~18, 16th; see table above). **qwen3.8:27b is the only single-24GB default-ctx=8192 completer** (DeltaNet's tiny KV footprint lets the step-3 prompt fit without a ctx override) and the first to also pass L6-full.

**Entities (L5, step 3) capability gap is A3B-MoE-architecture-specific, not generational or vendor-specific**: FAILS — qwen3.5:35b, qwen3-30b:2507, qwen3-coder:30b-1m (all Qwen3.5 A3B MoE lineage, confirmed 2026-08-13 at ctx=32768, genuine capability gap not a ctx-window artifact — coder fine-tunes inherit the base's gap). PASSES — qwen3.5:27b (dense, same generation as the A3B that fails — proves the gap is architectural not generational), all Qwen3.6-A3B variants (noctrex, unsloth, qwopus3.6, quest:35b), Gemma4 QAT (26b/31b), GLM4.7-flash. core/turret/combat PASS regardless — only step 3 (entities) discriminates.

**Node_paratrooper (L6-full) is config-sensitive to the GPU split, root cause confirmed — this is qwen3.8:27b's own investigation (CLOSED 2026-08-23) and the first-discovered instance of the broader cross-GPU floating-point sensitivity documented in Cross-Cutting Rules below.** Three GPU configs tested on the one irreplaceable original Q4_K_M file that first broke this wall (2026-08-15): single RTX 4090 **PASS** (45.5 tok/s, 103s, MD5-identical across repeats — genuine determinism); 2×24GB 3-GPU auto-dist (no explicit tensor_split) **PASS** (10.1 tok/s, 453s); 2×24GB explicit `tensor_split=1|1` (the config in `2x24gb.txt`) **reproducibly FAILS** (3 runs, 28.2-28.3 tok/s, TESTS_STILL_FAIL every time); 3×24GB explicit `tensor_split=1|1|1` **PASS** (9.6 tok/s, 474s, CONFIRMED 2026-08-16, one run, not re-verified for reproducibility). **Root cause, confirmed by diffing the generated `game.js` with `--keep-workdirs`**: lines 1-268 (constructor, spawning, input) are byte-identical between the single-GPU PASS and the 2-GPU FAIL; the first divergence is a naming choice at line 269 (loop variable `pr` vs `p`/`proj`) that cascades autoregressively and lands on wrong logic for the hardest test (33, freefall-lands-on-landed — the PASS version correctly checks horizontal distance + tracks `killedLanded`, the FAIL version checks full 2D distance with no kill tracking). **Isolating the trigger**: a degenerate `tensor_split=1|0` (100% on one GPU, through the multi-GPU code path) produces a BYTE-IDENTICAL output to true single-GPU — proving the divergence requires *actual* cross-device computation, not merely "using the tensor_split parameter". **Conclusion**: cross-GPU tensor-split causes a tiny floating-point reduction-order difference (summing partial activations across devices isn't bit-identical to single-device summation) that is usually invisible but can flip an extremely close top-1 greedy-decoding token choice, here at an early stylistic decision that cascades to broken logic later in the same generation — a known class of multi-GPU numerical non-determinism, not a capability regression. All other task groups (27/27: 19 coding + 4 web + 4 L6-stepped) are confirmed UNaffected by this at tensor_split=1\|1 — the effect is specific to node_paratrooper's long, complex from-scratch generation. Spot-checked 2 other models' documented paratrooper FAILs on a different GPU config (qwen3.6:27b, noctrex-qwen3.6:35b) — both FAIL on every config tested, confirming those are genuine large capability gaps, not qwen3.8:27b-style near-miss config sensitivity.
**File-specificity, investigation CLOSED 2026-08-23**: tested 6 independently-quantized Q4_K_M-tier-and-up builds of this same base model × 3 GPU configs. Only the ONE original file (now upstream-deleted and irreplaceable — do not delete the local copy, it was briefly, accidentally lost once already and recovered via pinned-revision + SHA256 verification) ever passes on both single-GPU AND 3-GPU. Every other build (unsloth Dynamic V3 at Q4_K_M/Q5_K_M/Q8_K_XL, unsloth's older-pipeline Q8_0, bartowski Q4_K_M) FAILS on every clean config tested. bartowski's Q5_K_M is the only other build with any clean PASS (single-GPU 5/5) but FAILS 5/5 at 3-GPU, so it does not share the original's split-independence. `python_hashmap` PASSES on every build regardless (f16 KV rule unaffected). **"First model to pass node_paratrooper" is a property of one specific GGUF file, not the Qwen3.8-27B/Gated-DeltaNet architecture — there is no "right precision" or "right quant house" fix.** Practical recommendation: use bartowski's Q5_K_M (`qwen3.8:27b-q5km`) single-GPU if you don't have the irreplaceable original; use the original if 3-GPU capacity is available. Full build-by-build detail in `models/candidates.txt` (`qwen3.8:27b-ud`, `qwen3.8:27b-bartowski`) and `memory/project_benchmark_findings.md`.

**Scout/engine-regression housekeeping notes**: `dotnet_sas` net8→net9 fix (2026-06-21) — both csproj files targeted `net8.0` but the host runs .NET 9.0.17; all prior dotnet_sas failures across every model predating this fix were false negatives (preflight.sh now requires .NET 9+; treat any older dotnet_sas failure as suspect). MoE weight quantization experiment (2026-06-22): qwen3.5:35b Q6_K vs Q4_K_M produced identical failures (hashmap+tokenizer) at 36% slower speed — Q4→Q6 weight precision changes nothing for MoE capability; do not repeat this experiment for other MoE models. Always include the full contents of relevant files in prompts to prevent hallucinated file structure.

**CPU-MoE paging (llama-server)**: MoE models slightly over VRAM capacity can run via mmap paging — flags `-ngl 999 --n-cpu-moe N --no-repack`, keeping the expert FFN tensors of the first N layers CPU-resident (mmap'd, page-cached) while attention stays on GPU. **Must omit `no_mmap` from the model config** (it forces full RAM residency and defeats paging); add `n_cpu_moe=N,no_repack` instead — both pass through the existing underscore→hyphen flag converter, no code changes needed. Speed rule of thumb on 86GB DDR5 (~90GB/s): ~53 tok/s for A3B active, ~10 tok/s for A15B. Best fit: a model ≤4GB over the VRAM limit, so a small N (4-8 layers) sheds just enough to leave throughput near GPU speeds — dense models gain nothing (every weight touched every token = disk thrash). **Calibration lesson (gpt-oss-120b Fable-5, 2026-08-12)**: an initial n_cpu_moe=8 estimate was 4× too low — with tensor_split=1\|1\|1 the KV cache is also split across GPUs, so even 51MiB of KV on GPU2 OOM'd up to n_cpu_moe=24; n_cpu_moe=30 (32% of layers) was the first working value. Rule: for a model 3GB over budget, expect to offload ~30% of MoE layers, not ~8%. (Fable-5's own benchmark result is in the table above — rejected, no capability improvement over the base model.)

#### Cross-Cutting Rules & Precision Canaries

- **`python_hashmap` is a precision canary**: this L5 task is acutely sensitive to KV cache and
  quantization precision. With q8_0 KV or GPTQ INT4 (C4 calibration), models omit `_EMPTY = None`
  from the module-level definitions while correctly implementing the tombstone algorithm — a single
  wrong token at a precision boundary. With f16 KV (llama-server) or ollama's internal format,
  the same model passes cleanly. Use `cache_type_k=f16,cache_type_v=f16` for any 27B dense model
  whose python_hashmap fails with q8_0 KV. Do not change the task stub to paper over this.
  This precision sensitivity is specific to the qwen3.6:27b and qwen3.8:27b architectures (NOT all 27B models):
  qwen3.5:27b passes python_hashmap cleanly with q8_0 KV (confirmed 2026-06-27). qwen3.8:27b (DeltaNet hybrid)
  requires f16 KV for the same reason — confirmed 2026-08-15. Dense 32B Q4_K_M with q8_0 KV passes cleanly
  (qwen2.5-coder:32b-q4 confirmed 2026-06-18).
  Rule: use f16 KV for qwen3.6:27b and qwen3.8:27b; do not apply to other 27B models. bf16 KV has
  wider dynamic range at the same memory cost but has not been tested here — f16 has been stable and
  sufficient. Only worth trying if a model fails with f16 KV in an unexpected way. MoE models:
  Q4_K_M vs Q6_K confirmed identical scores for qwen3.5:35b (2026-06-22) — MoE weight
  quantization does not affect task outcomes; do not use higher MoE quant to fix failures.
  Also a capability discriminator: some models fail due to wrong tombstone logic regardless of
  quantization (noctrex-qwen3-coder:30b TESTS_STILL_FAIL, qwen2.5-r1:32b TESTS_STILL_FAIL,
  glm4.7-flash TESTS_STILL_FAIL, deepseek-r1:32b TESTS_STILL_FAIL, qwen3-30b:2507
  TESTS_STILL_FAIL, qwen3-coder:30b-mxfp4 TESTS_STILL_FAIL, glm4-tulu:32b TESTS_STILL_FAIL,
  qwen3-48b:a4b TESTS_STILL_FAIL, huihui-60b TESTS_STILL_FAIL,
  quest:35b TESTS_STILL_FAIL with llama-server 10094 f16 KV (was PASS with ollama 2026-06-24 — llama-server 10094 kq-mask regression specific to this model; entities PASS still confirms Qwen3.6 base; ⚠ UPDATE 2026-09-26 — on the current pinned 67a17c17c binary this task's result is itself GPU-split-dependent for quest:35b: 3/3 PASS single-GPU, 3/3 FAIL at 2×24 GB tensor_split=1|1, see the cross-GPU sensitivity paragraph below — treat any single-config result for this model+task as provisional),
  north-mini-code PASS, gemma4:26b PASS, gemma4:31b-qat PASS, qwen3.5-122b:a10b PASS), and thinking models exhaust their
  budget in reasoning before emitting code (mellum2:12b-thinking, qwq:32b, gpt-oss:20b on this task).
  Note: glm4-tulu:32b (dense 32B) fails despite being larger than glm4.7-flash (MoE 16 GB) which
  also fails — dense scale does not fix this gap for the GLM architecture. Gemma4 A4B (MXFP4 MOE)
  passes at 15.4 GB (confirmed 2026-07-22 at f16 KV). Gemma4 dense 31B QAT also PASS (confirmed
  2026-07-24 at f16 KV) — dense Gemma 4 architecture preserves L5 precision at Q4_0.
  qwen3.5-122b:a10b PASS (confirmed 2026-08-13, q8_0 KV) — A10B active-param tier clears the ceiling
  that blocks all A3B models. gpt-oss:120b also passes (thinking model, q8_0 KV).

- **Cross-GPU floating-point sensitivity is a general phenomenon, not a `node_paratrooper`/
  `ornith:1.0-35b` quirk — CONFIRMED 2026-09-26 via a targeted sweep.** Background: `node_paratrooper`
  had shown a reproducible single-GPU-PASS→multi-GPU-FAIL flip across 3 models (`qwen3.8:27b`,
  `qwen3.8-flash-next`, `ornith:1.0-35b`), and `ornith:1.0-35b`'s `python_hashmap` had just shown the
  *opposite* direction (single-GPU-FAIL→2-GPU-PASS) — raising the question of whether that was a
  fluke. Designed a sweep: picked 3 model+task pairs already known to be borderline for *other*
  reasons (documented binary-version-induced flips, unrelated to GPU topology) — `quest:35b` ×
  `python_hashmap`, `glm4.7-flash` × `python_config_loader`, `noctrex-qwen3.6:35b` ×
  `csv_nordic_property` — and ran each at both single-GPU and 2×24 GB `tensor_split=1|1`, 3×
  repeat-verified wherever a disagreement appeared. **Result: 2 of 3 pairs showed a genuine,
  fully-reproducible flip — one in each direction.** `quest:35b`/`python_hashmap`: 3/3 PASS
  single-GPU, 3/3 FAIL 2×24 GB (hurts, matching `node_paratrooper`'s usual pattern).
  `noctrex-qwen3.6:35b`/`csv_nordic_property`: 3/3 FAIL single-GPU, 3/3 PASS 2×24 GB (helps,
  matching `ornith:1.0-35b`'s pattern) — a **second** model+task pair in the helping direction.
  `glm4.7-flash`/`python_config_loader` showed no flip (FAIL on both configs) — not every
  borderline task is GPU-split-sensitive. **A 2/3 hit rate on a 3-pair sample pre-selected for
  borderline status is strong evidence this is a real, broad pattern**, not a two-off coincidence:
  cross-GPU floating-point reduction-order non-determinism at greedy decoding can flip *any*
  sufficiently close-call task result, in either direction, on any model, once real computation is
  split across ≥2 physical GPUs. Direction is not a property of the task or the model — the same
  task (`python_hashmap`) flips in opposite directions on different models (hurts `quest:35b`,
  helps `ornith:1.0-35b`), consistent with each case being its own coincidence of which specific
  token choice sits closest to the decision boundary for that exact model. **Practical
  implication: any single-GPU-only (or any single-config-only) benchmark result for a model that
  has EVER shown binary-version or precision sensitivity on a given task should be treated as
  provisional until verified at the GPU split it will actually be deployed on** — this extends well
  beyond `node_paratrooper`. Zero hwmonitor CRIT throughout.
  **Round 2 (5 more pairs — 3 borderline + 2 stable controls) CONFIRMED 2026-09-26: ZERO flips
  (0/5)**, a much steadier picture than round 1's 2/3. Tested: `quest:35b`×`python_multifile_rename`
  (FAIL/FAIL, stable), `qwen3.6:35b-A3B` unsloth × `csv_nordic_property` (FAIL/FAIL, stable —
  **notably, `noctrex-qwen3.6:35b`'s own flip on this exact task does NOT generalize to this other
  Qwen3.6-A3B build**, confirming the boundary-proneness is file-specific, not architecture-wide),
  `qwen3.8-27b-gsqrco-iq3xxs`×`python_hashmap` (PASS/PASS, stable), plus two controls anchored on
  `python_hashmap`: `qwen2.5-coder:32b-q4` (stable PASS, as predicted) and `glm4.7-flash` (stable
  FAIL, as predicted). **Combined hit rate across both rounds: 2 flips out of 8 pre-selected
  borderline pairs (25%)** — still clearly better than the stable controls' 0/2, so "pre-select
  for borderline history" remains a real, useful heuristic, just at a more modest hit rate than
  round 1's small sample suggested. Diminishing returns on further rounds unless new candidates
  surface naturally.
  **Round 3 (2026-10-04) — new dimension, not new pairs: does the flip hold at a 3-way GPU
  split, or is it 2-way-specific?** No new borderline candidates had surfaced since round 2, so
  rather than a fresh blind search, extended the two already-confirmed round-1 flips
  (`quest:35b`×`python_hashmap`, hurts; `noctrex-qwen3.6:35b`×`csv_nordic_property`, helps) to
  explicit 3×24 GB `tensor_split=1|1|1` — a split neither round 1 nor round 2 tested. **Result:
  both flips hold at 3-way exactly as at 2-way, 3/3 each** — `quest:35b`/`python_hashmap` FAILS
  at 3-way (matching 2-way FAIL, not the single-GPU PASS); `noctrex-qwen3.6:35b`/
  `csv_nordic_property` PASSES at 3-way (matching 2-way PASS, not the single-GPU FAIL). Neither
  pair shows a THIRD distinct behavior at 3-way — once cross-GPU computation is involved at all
  (2-way or 3-way), the result is stable in whichever direction that specific model+task pair
  already showed at 2-way; it's "single-GPU vs. any-multi-GPU" that matters for these two pairs,
  not the exact split arity. This contrasts with `node_paratrooper`'s own cross-GPU history
  (qwen3.8:27b: 2-way FAILs, 3-way PASSES — a genuine 3-way-specific difference) — confirming
  split-arity sensitivity is itself per-model-per-task, not a fixed rule. hwmonitor: zero
  WARN/CRIT across all 6 runs (max 40-59°C). Round 3 complete; no further rounds planned unless
  new candidates surface.
  **`ornith:1.0-35b`'s `csv_nordic_property` single-GPU anomaly: CLOSED 2026-09-26.** Replayed the
  exact original spot-check 4-task prefix (`python_safe_div → node_slugify → python_lru_cache →
  csv_nordic_property`, same server session, single-GPU) 3 times — PASSED 3/3, ruling out
  session/request-history state as the explanation (GPU-split sensitivity was already ruled out
  earlier). The task has now passed 9/9 times across every condition tested since the one original
  spot-check FAIL. No reproducible trigger found; not investigated further.
  Full result detail: `next-runs.md`'s 2026-09-26 sweep entries; `memory/project_benchmark_findings.md`.

#### Edit Protocol Enforcement

- Model output must be ONLY:
  - one or more `BEGIN_FILE path ... END_FILE` blocks
- Reject:
  - markdown fences
  - explanations
  - edits to non-allowed files
- If output is invalid, classify error and save a truncated snippet for debugging.

#### Task Authoring Rules

- Baseline tests MUST fail on unmodified `task_data/`.
- After the correct fix, tests MUST pass.
- Editable file allow-list should be as small as possible (ideally one file).
- Provide context files as needed (tests, config, package file).

#### Repository Layout (quick reference)

```
bench.py            CLI runner
install.sh          Interactive dependency installer
run.sh              Venv setup + bench.py wrapper; sources .gpu-mode; bootstraps a missing venv pip via ensurepip before installing requirements.txt (Debian/Ubuntu boxes without python3-pip otherwise hit a confusing externally-managed-environment error, see the Debian pip finding below; added 2026-09-24, test_run_sh_pip_bootstrap.py); auto-starts hwmonitor in background (--no-hwmonitor to skip); logs to logs/run-NN.log (run-latest.log symlink); BENCH_NO_LOG=1 prevents double-logging from compare.sh; in multi-GPU mode with 3+ GPUs, aborts before launching if power limits look unsafe for MAX_PSU_WATT (default 1200, override to match your PSU) — SKIP_POWER_CHECK=1 bypasses (added 2026-08-29 after a hard-crash incident, see hw-upgrade-july-2026.md)
gpu-mode.sh         List GPUs; toggle/set single vs. multi-GPU mode; writes .gpu-mode (gitignored, sourced by run.sh)
powerlimit.sh       GPU power cap; uniform mode (all GPUs, called by compare.sh) or --per-gpu (4090@300W, 3090@280W); WSL2-aware
compare.sh          Runs the canonical models/default.txt set (10 models as of 2026-09-15) (model-timeout 1200, num-predict 8000); auto-names output by backend (results-compare.json / results-compare-ls.json); sets BENCH_NO_LOG=1 to suppress per-run log duplication; logs to logs/compare-NN.log
compare-results.sh  Merge two result JSONs and print speed summary + full task table for backend comparison
statistics.sh       Aggregate all output/*.json into one sharable dataset: summary/detail/context-speed
                     tables, VRAM-scalability estimation, CSV/JSON export; --export bundles output/*.json
                     into a portable file, --import pulls an export (or a plain results file) back into
                     output/ on another machine — used to pull in the vLLM box's benchmark exports (see
                     docs/reports/qwen3.8-27b-nvfp4-2x-rtx5060ti-vllm-export.json)
fetch-hf.sh         Download GGUF files from HuggingFace Hub based on hf: fields in models/*.txt; pre-checks repos for 404/deleted before downloading
search-hf.sh        Search HuggingFace Hub for GGUF files; suggests models/*.txt lines to paste
scout-hf.sh         Periodic HF Hub scanner; diffs against saved state (output/hf-scout-state.json); use --vllm for AWQ/GPTQ/FP8 transformers repos (state: output/hf-scout-vllm-state.json); --no-save for dry-run; --show-all to include unchanged repos
preflight.sh        Dependency checker. Run it first on a new box: dotnet_sas needs .NET 9+
how-to-vllm.md      vLLM on an RTX 50xx (Blackwell) box: setup, GGUF plugin, model picks (models/16gb.vllm, models/2x16gb.vllm)
how-to-test-flash-next.md  Step-by-step: qwen3.8-flash-next on 16 GB VRAM + RAM + NVMe expert paging
test-plan-5060ti.md Plan for the RTX 5060 Ti box: qwen3.8-27b-gsqrco (llama-server) and first vLLM tests
vllm-plan.md        Copy-paste steps: Qwen3.5-9B AWQ on vLLM for agentic tool calling (RTX 5060 Ti 16 GB)
                    (the second-card upgrade lives in the serving repo:
                    ~/GIT/llm-service-provider/upgrade-dual-5060.md — tp=2 Qwen3.8-27B target,
                    capacity and DDR5 sizing, benchmark steps point back here)
docs/HOME_LAB_GUIDE.md     llama.cpp vs vLLM home-lab guide, recommended models by VRAM tier
next-runs.md        Referenced throughout this file and models/*.txt, but NOT tracked in git
                    (absent on the RTX 5060 Ti box as of 2026-09-15). See Known Issues.
hw-upgrade-july-2026.md    Hardware state/crash-incident log + VRAM-tier upgrade analysis for the
                    3-GPU rig; also NOT tracked in git. October 2026 addendum corrects the
                    "node_paratrooper never passes" premise and adds the vLLM-concurrency axis.
hwmonitor/
  hwmonitor.py      Live hardware watchdog: GPU temp/power/VRAM, CPU temp, RAM; WARN/CRIT on threshold breach; aborts bench.py on CRIT (SIGINT → SIGTERM)
  SPEC.md           hwmonitor specification and threshold reference
lib/
  tasks.py                Task definitions, prompt builder, subprocess helpers
  ollama_client.py        Ollama /api/chat client
  llama_server_client.py  LlamaServerManager (spawn/stop llama-server) + chat() for OpenAI-compatible API
  vllm_client.py          VLLMManager (spawn/stop vllm serve) + chat() for OpenAI-compatible API
  model_config.py         Parse models/*.txt 3-field format → ModelConfig dataclasses
  parsing.py              BEGIN_FILE/END_FILE parser + allow-list validator
  reporting.py            Comparison table (paginated), failure detail, JSON writer
  hw_snapshot.py          GPU/CPU/RAM snapshot (nvidia-smi, /proc/cpuinfo, /proc/meminfo)
  gpu_monitor.py          pynvml GPU telemetry; multi-GPU aware (sums VRAM across all handles, takes max of util)
  power_check.py          Pre-flight GPU power-limit safety check for 3+ GPU runs; evaluate() unit-tested in tests/test_power_check.py; called by run.sh (added 2026-08-29)
  history.py              Run history writer and header printer
  test_results.py         Partial credit: per-test outcomes from runner output → weighted score (record test_score; added 2026-10-08)
logs/
  run-NN.log          Per-run output (tee from run.sh); keeps last 10; run-latest.log symlink
  compare-NN.log      Per-compare output (tee from compare.sh); compare-latest.log symlink
llamacpp/
  build-llama.sh      Build helper (symlinked as ~/GIT/llama.cpp/my-build.sh) — detects CUDA/GPU
                      archs, builds with -DGGML_CUDA=ON -DGGML_CUDA_GRAPHS=ON (added 2026-09-04,
                      required for GGML_CUDA_GRAPH_OPT=1 to do anything — see qwen3.8-flash-next
                      notes below), optional install + systemd service prompts
  README.md           Setup checklist, architecture minimum-commit table, troubleshooting
tests/
  test_parsing.py             Parser unit tests  →  python3 -m pytest tests/
  test_model_config.py        Model config parser unit tests
  test_llama_server_client.py llama_server_client._parse_body unit tests (reasoning_content, timings, content/thinking split) + foreign-port-occupant startup guard + LLAMA_SERVER_PORT env override
  test_llama_server_flags.py  _bool_flag unit tests (--load-mode none vs legacy --no-mmap, by binary --help support)
  test_harness_e2e.py         End-to-end mock-chat_fn self-test of run_one() + comparison table + skill-level logic
  test_power_check.py         lib/power_check.evaluate() unit tests
  test_export_task.py         --export-task bundling unit tests; also pins the TASK.md format that
                              llm-service-provider's `selftest.sh --bench` parses ("## Files you may
                              edit" bullets, the fenced line under "## Check your work", **Setup:**)
  test_hwmonitor.py           hwmonitor threshold state-machine unit tests
  test_reporting.py           lib/reporting skill-level scoring unit tests
  test_hw_snapshot.py         hw_summary unit tests (results header names the right serving engine)
  test_statistics_server_name.py  statistics._server_name unit tests (llama_server_ver column attribution)
  test_powerlimit_output.py   powerlimit.sh WSL2 PowerShell one-liner regression test (skipped off-WSL2)
  test_run_sh_pip_bootstrap.py  run.sh venv/pip setup regression guard (ensurepip fallback, venv-python pip invocation — see Debian pip finding below)
  test_test_results.py        partial-credit parsing (xunit/node:test/pytest per-test lines + summary counts) and weighting
  test_unity_shim_sync.py     gamedev guards (incl. every test_weights key names a real test): per-task UnityEngine shim copies match task_data/_shared/UnityShim,
                              every gamedev task has a *.reference.* solution, parity fixtures match the JS spec
task_data/
  python_safe_div/        L1 Python pytest task (19 coding tasks total, L1–L5)
  csv_nordic_property/    L3 data task: implement solution.py against 5 000-row Nordic CSV; min_predict=20000 num_ctx=32768 model_timeout=600
  context_8k/             L1 context retrieval at ~5.5k tokens (6 context tasks total)
  multihop_forward/       L3 two-hop retrieval (multihop_reverse is its mirror task)
  distractor_notes/       L2 decoy-resistant retrieval
  multihop_chain_5/       L4 5-hop config inheritance (correct answer: 90; sibling distractor: 45; top-level distractor: 30)
  multihop_cross_5/       L4 5-doc cross-reference (correct: oncall-emea-w-high; criticality distractor: oncall-emea-w-crit)
  _shared/UnityShim/      canonical minimal UnityEngine shim (Vector3, Quaternion, Mathf, Debug); copied into each
                          C# gamedev task's shim/ (task dirs must stay self-contained); never a task itself
  cs_*/, crossplay_*/     gamedev C# tasks: GameClient.sln, src/ at netstandard2.1 + LangVersion 9.0 (Unity's
                          constraints), xunit tests at net9.0; reference solutions are *.reference.cs (excluded
                          from compile and from --export-task)
  node_room_authority/, node_seat_reconnect/   gamedev Node tasks (node:test, no npm deps)
Task groups (--task-group):
  coding    19 coding tasks (L1–L5)
  web       4 web tasks (Express/FastAPI)
  l6 / para 4 stepped Paratrooper tasks (L3–L6; 'para' is alias for 'l6')
  l6_full   1 from-scratch Paratrooper task (node_paratrooper; needs --num-predict 24000)
  context   6 context retrieval tasks (8k–256k)
  multihop  5 multihop + distractor tasks (2-hop forward/reverse, 1 distractor, chain_5, cross_5)
  spot      10-task candidate spot check (standard evaluation subset)
  gamedev   9 Unity-client C# + Node-authority tasks (L2-L5), derived from the user's multiplayer games;
            OPT-IN (lib/tasks.py OPT_IN_GROUPS): excluded from a run with no --tasks/--task-group
            (boombrawl, CarrierDominion, RetroMultiCiv, Fireline); see "Game-dev task group" below
```

#### Pre-flight: check for an active external-facing serving instance

The sibling repo `~/GIT/llm-service-provider` (separate git repo) may be actively serving
llama.cpp or vLLM to a remote agent pipeline through an SSH tunnel on this same rig's GPUs —
that is its entire purpose, not benchmarking. **Before starting any GPU-consuming run in this
repo** (`run.sh`, `compare.sh`, or any `--task-group` run that spawns llama-server/vllm),
check whether it is active:

```bash
~/GIT/llm-service-provider/status.sh
# equivalent: ~/GIT/llm-service-provider/bin/llmctl status
```

Look at the `backend:` line and the `llm-backend` / `vllm-local-*` unit states — if active, a
benchmark run here will compete for the same GPU VRAM/compute and can disrupt real external
traffic being served through the tunnel. Coordinate before launching a benchmark (stopping it
via `llmctl stop backend` there would interrupt a live remote pipeline, so don't do that
unilaterally — check with whoever/whatever depends on it first).

**On the RTX 5060 Ti box this is no longer hypothetical**: its units are enabled, so a lane is
serving on boot and holds most of the 16 GB card. Since 2026-09-16 that lane may be **llama-server
running `qwen3.8-flash-next`** (this repo's own 37/38 model, served through
`profiles/rtx5060ti/models.ini` with `--fit` + NVMe expert paging, ~10.5 GB VRAM and ~75 GB of page
cache) rather than the vLLM 9B — check `backend:` in the status output, because the flash-next lane
competes for page cache as well as VRAM, and a benchmark started beside it will thrash both. `bin/llmctl stop` frees the GPU (the gateway and
its request log stay up, and the pipeline would get a 503); `bin/llmctl start` puts it back. Its
tunnel is disabled for now, so stopping the backend there disrupts only local clients.

**Port collision, not just GPU contention (confirmed 2026-09-24):** `llm-service-provider`'s
`llm-gateway` binds `127.0.0.1:8080` — the exact same fixed port `lib/llama_server_client.py`
always used for its own llama-server subprocess. If that gateway is active and you run a
llama-server-backend benchmark, `LlamaServerManager._start()`'s readiness poll used to succeed
instantly against the *gateway* instead of your own (never-actually-bound) subprocess, and every
task then failed with a misleading `TOOL_ERROR: model 'None' not found` that looks like a
model/task problem, not an infra one. Fixed: `_start()` now checks for a foreign `/health`
responder before spawning and raises loudly instead (`tests/test_llama_server_client.py::
test_start_refuses_foreign_occupant`); the port is also overridable via `LLAMA_SERVER_PORT` for
running llama-server-backend benchmarks alongside an active gateway. **Since 2026-10-08 the harness
default IS 8099** (`lib/llama_server_client.py`), so no override is needed next to the gateway. The guard had a hole until
2026-10-08: with its backend down the gateway answers `/health` with **503**, and `HTTPError` (a
`URLError` subclass) was swallowed as "port free", so llama-server then died on "couldn't bind
:8080". Any HTTP answer now counts as occupied (the test covers 200 and 503). **This means any past
llama-server-backend benchmark result recorded while the gateway happened to be active is
suspect** — it would have failed loudly as TOOL_ERROR post-fix, so a suspiciously bad/uniform
result predating 2026-09-24 alongside `llm-service-provider` being live is worth re-running, not
trusting as-is.

#### Known Issues

- **`bench.py` has no hwmonitor integration at all — it is `run.sh`-only, confirmed 2026-10-03.**
  hwmonitor is started/stopped by `run.sh` around its call into `bench.py`; invoking `bench.py`
  directly (e.g. for a quick targeted task without the `run.sh` wrapper) silently runs with zero
  hardware monitoring — there is no equivalent flag on `bench.py` itself to opt back in. Given
  this rig's documented hard-crash history under sustained multi-GPU load (see
  `hw-upgrade-july-2026.md`) and the standing "hwmonitor always on" practice, prefer `./run.sh`
  over bare `python bench.py` for any real GPU-consuming run, even a single targeted task —
  reserve direct `bench.py` calls for `--list-tasks`/`--export-task`/other non-GPU operations.
- **FIXED 2026-09-16: `--no-mmap` removal in mainline llama.cpp past `14a9d09f7`** (2026-09-09):
  upstream removed `--mmap`/`--no-mmap`/`--mlock`/`--direct-io`, replaced by
  `--load-mode {auto,none,mmap,mlock,mmap+mlock,dio}`, and every `models/*.txt` file uses `no_mmap`.
  `lib/llama_server_client.py` (`_bool_flag`) now reads each binary's `--help` once: if it lists
  `--load-mode` it emits `--load-mode none`, otherwise the legacy `--no-mmap` (release 10094, the
  unsloth fork). `none` is exactly what `--no-mmap` set (`common/arg.cpp:2705`:
  `load_mode = value ? MMAP : NONE`). The pinned `67a17c17c` has both flags and gets
  `--load-mode none`. Tests: `tests/test_llama_server_flags.py`. Evidence, in case the wording is
  questioned again (it was, 2026-09-16): `14a9d09f7`'s subject says "officially deprecate" but the
  commit is 86 deletions removing the argument definitions, and `git grep no-mmap 14a9d09f7 --
  common tools` finds nothing; the DEPRECATED warnings came earlier, with the `--load-mode` PR. Only `no_mmap` is translated; no
  model file uses `mlock` or `direct_io`. Still to do on a rebuild: `llm-service-provider`'s
  `presets/models.ini` passes `no-mmap = true` straight to the router (comment added there).
- **`next-runs.md` is not in git.** 28 references across 10 files (this file, models/*.txt,
  ARCHITECTURE.md, SPEC.md, docs/HOME_LAB_GUIDE.md, llamacpp/README.md, ...) point at it, but it
  was never committed, so a fresh clone (e.g. the RTX 5060 Ti box) doesn't have it. Commit it from
  the machine that has it, or treat those references as dangling.
- **New box: run `./preflight.sh` before the first benchmark.** The RTX 5060 Ti box had only .NET
  SDK 8, so `dotnet_sas` failed as TOOL_ERROR in 0.9s: a false negative that looks like a model
  failure in the results table. Fixed by installing `dotnet-sdk-9.0`.

#### How to Run

```bash
# Install missing dependencies interactively
./install.sh

# Check all dependencies
./preflight.sh

# Full benchmark (models/default.txt set × 39 tasks; gamedev's 9 are opt-in via --task-group gamedev)
./compare.sh

# Single model / subset of tasks
./run.sh --models qwen2.5-coder:7b --tasks python_safe_div

# See what tasks exist — id, difficulty, group, description — before picking one to export
python3 bench.py --list-tasks

# Export a task as a shareable, self-contained package (TASK.md + PROMPT.txt + starting files)
# for another coding agent to attempt directly — no model/backend needed for this mode.
python3 bench.py --export-task node_paratrooper --export-dir ~/share/l6-full-challenge

# Same, to a scratch dir — the L6-full task, the hardest in the benchmark (see CLAUDE.md above)
python3 bench.py --export-task node_paratrooper --export-dir /tmp/mytestdir

# Any other task works the same way — e.g. the L5 precision-canary task
python3 bench.py --export-task python_hashmap --export-dir /tmp/mytestdir-hashmap

# Run the harness's own unit tests — MUST activate the venv first (see note below)
source .venv/bin/activate && python -m pytest tests/ -v
```

**Always activate `.venv` before running pytest directly** (`source .venv/bin/activate && python
-m pytest tests/`), don't invoke `.venv/bin/python3 -m pytest` or a system `python3 -m pytest`
by path. Two failure modes if you skip this, both confirmed 2026-09-06: (1) system `python3` has
no `pytest` installed at all → immediate `No module named pytest`; (2) invoking pytest via
`.venv/bin/python3` directly (without activating) passes 93/94 but spuriously fails
`test_harness_e2e.py::test_run_one_pass` — that test's mock coding task shells out to run
`python -m pytest` inside a scratch workdir, and its `shutil.which("python")` PATH-detection
fallback reflects the *invoking shell's* PATH, not the interpreter you launched pytest with;
without `.venv/bin` on PATH it falls back to bare `python3`, which is the same pytest-less system
interpreter from failure mode (1). `run.sh` always sources the venv first, so this never affects
real benchmark runs — it only bites ad hoc `pytest` invocations that skip activation.

#### Deliverables Expectations

When asked to implement features:
- Provide a minimal working implementation first.
- Add at least one test for any non-trivial parser or scoring logic.
- Update `SPEC.md` / `ARCHITECTURE.md` if behavior changes.

#### vLLM backend constraints (updated 2026-07-06)

- **2× RTX 5060 Ti, Qwen3.8-27B NVFP4 at tp=2 — CONFIRMED 2026-09-23/24** (`models/2x16gb.vllm`).
  `qwen3.8-27b:nvfp4-next` (vLLM bbd7c24d6e via `VLLM_BIN=~/vllm-env-next/bin/vllm`, W4A4
  FlashInferCutlass kernel, FlashInfer GDN prefill, CUDA graphs): **spot 10/10 at 32.6 tok/s**, incl.
  python_hashmap (PASS ×2 — 4-bit activations do NOT trip the canary on this QAT checkpoint) and
  node_paratrooper (PASS once, 134 s; unrepeated, treat as a data point). The same model on the
  2026-09-06 build ran W4A16 (spot 9/10, 30.0 tok/s): builds before 2026-09-08 lack `13cf9e05c1` and
  `f6326f53bd`, silently. Always read the server log's `for NVFP4 GEMM` line. Harness entries for
  this model need `language_model_only,max_num_seqs=4` or startup OOMs on 16 GB cards. vLLM runs
  need `LLAMA_MODELS_DIR` exported even for HF-format models (bench.py refuses to start without it).
  Serving-side A/B (throughput, TTFT, KV 155,830 tokens): `~/GIT/llm-service-provider/upgrade-dual-5060.md` Step 6.
  Shareable report in `statistics.sh` format plus an export bundle (full run, 128k run, dotnet_sas rerun):
  `docs/reports/qwen3.8-27b-nvfp4-2x-rtx5060ti-vllm.md`. A curated `--export` (the CLI bundles all of
  `output/`) is made by setting `lib.export.OUTPUT_DIR` to a directory holding only the chosen files.
  **FULL RUN 2026-09-24**: coding 19/19, web 4/4, L6 stepped 4/4, context 8k-128k 5/5 (context_128k
  PASS in 71 s at tp=2 vs 1,542 s on one 4090 with llama.cpp), multihop 5/5; node_paratrooper 1/7
  runs (the spot PASS did not repeat). dotnet_sas needs .NET 9: on this bare-metal Ubuntu it lives in
  `~/.dotnet` (dotnet-install.sh), so put `$HOME/.dotnet` FIRST on PATH (`/usr/bin/dotnet` is 8.0).

- **⚠ SUPERSEDED 2026-09-06 — GGUF support moved out-of-tree, no patch needed anymore.**
  Checked a fresh `~/GIT/vllm` checkout (merged from upstream `main` 2026-09-06): the in-tree
  GGUF kernels this "ally's patched flag" note describes were deleted upstream back in June
  2026 (`6635279d8a`, "Migrate GGUF quantization support to plugin") and replaced with an
  official, separately-maintained `vllm-project/vllm-gguf-plugin` package. Plain
  `vllm serve <repo>:<quant_type>` now works — no `--quantization gguf` patch flag needed at
  all. The plugin **natively supports MoE for Qwen3-MoE and Qwen3.5-MoE** (our own model
  lineage) plus DeepSeek-V2/V3 and MiniMax-M2. Two things to know: (1) use K-quants (Q4_K_M,
  Q6_K) for MoE models, not I-Matrix quants (IQ1_M/IQ2_M/IQ3_S/IQ4_XS) — I-Matrix expert layers
  fall back to a slow per-token loop instead of the fast fused MoE kernel, and every model this
  repo has actually promoted is already a K-quant; (2) Qwen3.5-MoE GGUF specifically needs
  `--hf-config-path` pointing at the equivalent HF model, since its `qwen35moe` architecture
  string isn't recognized by HF's own config parser. Neither the plugin nor core vLLM require
  Blackwell/RTX 5000-series hardware for this — `CMakeLists.txt` lists this rig's actual
  compute capabilities (8.6/8.9) as fully supported, and a recent plugin fix ("remove Blackwell
  bf16 restriction") turned out to be unlocking Blackwell to match a path Ampere/Hopper already
  had, not gating anything to Blackwell. **Separately**, this same vLLM checkout now ships a
  native Anthropic Messages API (`vllm/entrypoints/anthropic/`, routes `/v1/messages` and
  `/v1/messages/count_tokens`, matching mainline llama.cpp's own native support) — relevant if
  this harness or any sibling tooling ever needs to speak Anthropic format directly to a
  vLLM-served model instead of going through `vllm_client.py`'s existing OpenAI-compatible
  path. Re-benchmarking the old 15/16-at-31.2-tok/s result below against the new plugin has not
  been done — treat the numbers below as historical (they may well be faster now) until
  someone re-runs it.
- **Plugin update reviewed 2026-09-06** (21 new commits since the above check). Most relevant:
  a **real OOM fix directly hitting our 27B tier** — commit `51b8d7a` ("Release GGUF shard
  tensors when materializing fused weights") fixed fused-layer shard tensors (QKV, merged-
  column) being kept resident twice during loading. Its own commit message gives exact numbers
  for a **27B Q4_K_M GGUF** (our `qwen3.6:27b`/`qwen3.8:27b` weight class): 17.83 GiB of weights
  was ballooning to 22.87 GiB peak and OOM-ing on a 24 GB card; fixed, peak now 19.24 GiB, loads
  with real headroom. A 27B-class GGUF that likely could not load on this plugin a few weeks ago
  should now fit on a single RTX 4090 — worth an actual test before assuming the old 4×
  llama-server-vs-vLLM speed gap still holds at this weight class. Also landed: **Qwen3.5/3.6
  MTP + Gated DeltaNet support** (`4ec8d61`) — dedicated adapters auto-detect an embedded
  `nextn` MTP block in the GGUF (`--speculative-config '{"method":"mtp",...}'`, no separate
  file, same clean pattern already confirmed at zero speed penalty on `qwen3.5-122b:a10b` via
  llama.cpp) plus explicit Gated DeltaNet weight-layout reordering — directly the architecture
  family behind our best single-GPU models, though the adapter's `model_type` map only lists
  `qwen3_5*` strings explicitly and the plugin's own "tested coverage" docs only exercise Qwen
  3.6 in its vision-language form, not this plain-text/MTP path — present in code, not yet in
  their own regression-tested list. Also: Gemma4 GGUF support (`d4c1f0d`, relevant to
  `gemma4:26b-qat`/`31b-qat`), Mellum2 support (`fb973ad`), and CVE-2026-53923 already patched
  in this checkout. Full detail in `next-runs.md`.
- **Recommended first models to try on the vLLM GGUF plugin, by VRAM tier (2026-09-11, not yet
  vLLM-tested — recommendation, not a result)**: the plugin's own README "Tested model coverage"
  table (`~/GIT/vllm-gguf-plugin/README.md`) lists confirmed-working text architectures as Qwen
  2.5 (Q6_K), Qwen 3 dense (Q8_0), Phi 3.5 (IQ4_XS), GPT-2/StableLM (Q4_K_M), Gemma 3/OLMoE
  (Q4_0) — **notably, MXFP4 does not appear anywhere in that table**, and the Qwen3.5/3.6 GDN
  hybrid family and Gemma4 are only confirmed in vision-language form, not plain text/MTP. That
  means most of this repo's best-scoring small/mid models (`glm4.7-flash`, `ornith:*`,
  `quest:35b`, `qwopus3.6:35b`, `noctrex-qwen3.6:35b` — all MXFP4) carry real, untested
  architecture/quant-compatibility risk on this specific plugin, separate from whether they'd
  perform well once loaded.
  - **16 GB single GPU: `qwen2.5-coder:14b`** (Qwen2.5 architecture, Q4_K_M, ~9 GB weights —
    hf:`bartowski/Qwen2.5-Coder-14B-Instruct-GGUF`). Same architecture family the plugin
    explicitly lists as tested (Qwen 2.5), leaving comfortable VRAM headroom for vLLM's own
    loader overhead + KV cache at 16 GB. Not this repo's highest-scoring 16 GB-class model on
    llama-server, but the safest bet for an actual load-and-run success on a first vLLM-GGUF
    attempt — a model that won't load is worth nothing regardless of benchmark score.
  - **2× 16 GB (32 GB, tp=2): `qwen2.5-coder:32b-q4`** (Qwen2.5 architecture, Q4_K_M, ~18.5 GB
    weights — hf:`bartowski/Qwen2.5-Coder-32B-Instruct-GGUF`, PERFECT 19/19 coding on
    llama-server, this repo's strongest coder overall). Same architecture-confidence rationale as
    above, now with real headroom to spare at 32 GB for KV cache and vLLM's loader overhead, and
    the best documented capability of any model that fits this VRAM budget with a confidently
    supported architecture.
  - **Runnable entries since 2026-09-14, AWQ ones run 2026-09-15 (below)**: `models/16gb.vllm` (the 14B smoke
    test) and `models/2x16gb.vllm` (`qwen3.8-27b:nvfp4` via `QUASAR-QAT/Qwen3.8-27B-QUASAR-NVFP4`,
    plus the 32B fallback), for an RTX 5060 Ti box. Qwen3.8-27B does not fit a single 16 GB card:
    every NVFP4 build found is ~17-23 GB of weights. **qwen3.8-flash-next is not a vLLM target on
    consumer hardware**: vLLM main added its architecture in 2026-09, but the official recipe
    budgets ~250 GB aggregate VRAM. On 16 GB it runs via llama-server instead (see the
    qwen3.8-flash-next entry below). Details: `how-to-vllm.md` §6c; test plan: `test-plan-5060ti.md`.
    In GGUF mode the harness passes `hf:` as `--tokenizer`, so a `.vllm` GGUF entry must name the
    ORIGINAL model repo (e.g. `Qwen/Qwen2.5-Coder-14B-Instruct`), not a GGUF-only repo such as
    bartowski's, which has no tokenizer files. Download the GGUF through a `models/*.txt` entry.
    **Updated 2026-09-15**: the first smoke test is now AWQ on stock vLLM
    (`Qwen/Qwen2.5-Coder-7B/14B-Instruct-AWQ`, no plugin), which avoids compiling the plugin's
    CUDA extension on a box where PyTorch is CUDA 13.0 but `nvcc` is 12.8. Install vLLM from
    upstream `main` with `VLLM_USE_PRECOMPILED=1`: `13cf9e05c1` (prefer W4A4 NVFP4 kernels on
    SM120/121) and `f6326f53bd` (FlashInfer Gated DeltaNet prefill on SM12x) are not in the
    0.29.0 release. The harness never tests tool calling, so the plan adds a manual tool-call
    check (`--enable-auto-tool-choice --tool-call-parser hermes` for Qwen2.5-Coder). vLLM `main`
    also gained `--engram-config '{"cpu_offload": true}'` (`3116c5d06b`) for Flash-Next's n-gram
    table, which doesn't change the verdict: its main model still needs far more than 32 GB.
    **First smoke test (2026-09-15) hung on a stalled Hugging Face Xet download** (weights frozen
    at 1.0 GB, process asleep, no error). Fix: `HF_HUB_DISABLE_XET=1`, which `lib/vllm_client.py`
    now sets by default for servers it starts, as `lib/fetch_hf.py` already did. FlashInfer's
    `SM 12.x requires CUDA >= 12.9` warning means FlashInfer's JIT builds can't target SM120 with the
    system CUDA 12.8. Pointing `CUDA_HOME` at the pip `nvidia/cu13` folder does NOT work: its nvcc is
    13.4 but its headers are 13.0, which CCCL rejects ("CUDA compiler and CUDA toolkit headers are
    incompatible"). Install `cuda-toolkit-13-0` (matches PyTorch's CUDA 13.0, within the driver's
    13.1) and set `CUDA_HOME=/usr/local/cuda-13.0`; until then `VLLM_USE_FLASHINFER_SAMPLER=0` lets
    simple models start.
    More from that smoke test: the build helper is `/mnt/c/GIT/vllm/my-build.sh` (in the vLLM
    checkout, not this repo). Never run `vllm serve` from inside that checkout: its stale kernels
    shadow the build. The harness's token fallback now reads `HF_TOKEN.txt` (gitignored), then legacy
    `hf-token.txt` (now also gitignored; it wasn't before). Under WSL, vLLM leaves pinned memory
    off by default (expected startup warning). **Corrected 2026-09-16**: this is a default, not a hard
    block — `CudaPlatformBase.is_pin_memory_available` (`vllm/platforms/cuda.py`) turns it on when
    `VLLM_WSL2_ENABLE_PIN_MEMORY=1` and the WSL2 kernel is >= 4.19.121 (this box runs 6.6.87); only
    older kernels are refused outright. So it does not by itself rule out `--engram-config
    cpu_offload`, though Flash-Next still needs far more than this box's VRAM either way. Don't trust
    `/proc/<pid>/environ` for vLLM processes: `setproctitle` overwrites the start of it. Slow downloads
    that day (~1.2 MB/s) were the network (off-site Wi-Fi), not vLLM, Xet or the token. Full list:
    the troubleshooting section of `test-plan-5060ti.md`. A manual `vllm serve` also needs the venv
    activated: FlashInfer JIT-compiles its sampler during warmup and calls `ninja` from
    `~/vllm-env/bin` (the harness puts that folder on PATH itself).
    **FIRST WORKING vLLM RESULT on the RTX 5060 Ti (2026-09-15, by hand; harness run B4: 14B AWQ `python_safe_div` PASS, 33.5 tok/s)**:
    `Qwen2.5-Coder-7B-Instruct-AWQ` serves at 75-81 tok/s (streaming TTFT 50 ms, KV 119,760 tokens
    at 0.90 memory use), with `CUDA_HOME=/usr/local/cuda-13.0` after installing `cuda-toolkit-13-0`.
    Tool calling with `tool_choice=auto` fails: the 7B model wraps calls in `<tools>` instead of
    `<tool_call>`, so the `hermes` parser misses them; `tool_choice=required` or a named function
    works. Under WSL mirrored networking, `curl` to `127.0.0.1:8000` hangs for vLLM (bound to
    `0.0.0.0`); use the box's address. Details: `test-plan-5060ti.md` B3 and Troubleshooting.
    `Qwen2.5-Coder-14B-Instruct-AWQ` (same day): 43-44 tok/s, TTFT 53 ms, KV 9,152 tokens at
    `--max-model-len 8192 --gpu-memory-utilization 0.92`. 0.95 can't start: Windows holds ~1.1 GiB of
    the card, which `nvidia-smi` inside WSL doesn't show (check `torch.cuda.mem_get_info()`). Tool
    calling fails with `tool_choice=auto` exactly like the 7B (a system prompt only changed `<tools>`
    to `<json>`), so the Qwen2.5-Coder family needs `required`/named tool choice for agentic use.
    **Agentic pick: `cyankiwi/Qwen3.5-9B-AWQ-4bit`** (same day, by hand, `--tool-call-parser qwen3_coder
    --reasoning-parser qwen3`): tool calls PASS with `tool_choice=auto` (thinking on and off), plus
    required, named, a tool round trip and a no-tool question. ~60 tok/s, TTFT 40 ms, 7.55 GiB weights,
    KV 127,272 tokens at 0.92 with `--max-model-len 32768` on that day's build (Gated DeltaNet
    hybrid). **MEASURED PROPERLY 2026-09-17**: the KV pool is **6.75 GiB = 209,615 tokens** and is
    essentially independent of `--max-num-seqs` — 8 slots costs 0.03 GiB (0.5%), A/B/A/B with each
    start gated on an idle GPU, reproducing to the token. The 127,272 figure is NOT reproducible on
    the current build at any setting (even 32k/default gives 178,086); treat it as stale. The trap
    that produced it: servers started back-to-back measure whatever VRAM the previous one has not
    finished releasing, so always wait for `nvidia-smi` to show an idle card before comparing two
    configurations. Steps and results: `vllm-plan.md`. Harness
    entry `qwen3.5:9b-awq` in `models/16gb.vllm`, not yet run (the harness passes any param, `reasoning_parser`
    included, to `vllm serve`). Every `vllm serve` shell needs
    `CUDA_HOME=/usr/local/cuda-13.0`: `~/.bashrc` puts CUDA 12.8 first on PATH, and without it FlashInfer
    fails with a misleading `FlashInfer requires GPUs with sm75 or higher`. 2026-09-16: the
    `llm-service-provider` selftest (Claude Code through its gateway, served as `local-coder`, 65536)
    PASSES in 4 turns and 20 s; Claude Code accepts vLLM's thinking blocks, and prefix caching brings
    time to first token from 7.0 s to ~0.8 s. Now built in as that repo's machine profile `rtx5060ti`
    (one vLLM process for both lanes; `smoke.sh` checks the health status code now): smoke 9/9 and
    selftest both lanes PASS through `serve-vllm.sh` + the gateway. Its systemd units are installed and
    running on that box since 2026-09-16 (`llm-gateway` + `vllm-local-coder`, enabled at boot), so the
    lane holds most of the card: run `~/GIT/llm-service-provider/bin/llmctl stop` before benchmarking
    there. Since 2026-09-16 that lane may instead be llama-server serving `qwen3.8-flash-next`
    (~10.5 GB VRAM plus ~75 GB of page cache) — check `backend:` in its status output. Its `awtunnel` was disabled (`TUNNEL=off`) until the Hetzner host had that box's key; since
    2026-09-24 the tunnel is on and the remote pipeline sends real work to its `local-coder` lane, so a
    benchmark there must stop that lane first (`llmctl stop`, which the pipeline sees as a 503) or be
    coordinated (`./tunnel.sh off` keeps the pipeline out while you benchmark). Also 2026-09-16: that lane now serves a real
    agent all day through `~/GIT/pi-local-dev` (Pi 0.85.1 on Node 22, provider `llm-service-provider`,
    model `local-coder`) — a 79-message games session ended 42 turns on `toolUse` with no token-ceiling
    stop, which is the agentic-use evidence this benchmark itself cannot produce. Two facts from that:
    the lane emits reasoning on every turn whatever the client's thinking setting (the backend lever is
    `--default-chat-template-kwargs '{"enable_thinking": false}'`, which would cover both lanes here),
    and `llmctl stats` records OpenAI-style clients as `kind = chat` with full token/stop/tool detail
    since that day's gateway fix, while `llmctl status` names the model behind each lane.
  - **`qwen3.8-27b:nvfp4-next` CONFIRMED 2026-09-24/25** — the actual benchmark run this whole
    `models/2x16gb.vllm` target was built toward. QUASAR-QAT NVFP4 W4A4, `tp=2`, vLLM main
    (`0.30.1rc1.dev68+gbbd7c24d6`): **27/28 effective coding pass, `python_hashmap` passes
    despite 4-bit activations, ~32 tok/s single-stream, context clean through 128k.**
    `node_paratrooper` (L6-full) borderline (1/7) — the same cross-GPU tensor-split fragility
    already confirmed for `qwen3.8:27b` on llama.cpp, now confirmed on vLLM's `tp=2` path too
    (cross-engine, not an llama.cpp quirk). Real concurrency data from the serving deployment:
    ~35 tok/s at 1 concurrent agent, ~51 tok/s aggregate at 8. `models/2x16gb.vllm` updated with
    the exact config that was run (dropped `enforce_eager`, added `language_model_only` +
    `max_num_seqs=4`). Full writeup: `reports/models-status-Sept-2026.md`'s dedicated vLLM
    section; the raw runs + a shareable `statistics.sh`-format report are now also in
    `docs/reports/qwen3.8-27b-nvfp4-2x-rtx5060ti-vllm-export.json` and `...vllm.md` (pulled
    into this repo 2026-10-04 from the vLLM box) — `./statistics.sh --import
    docs/reports/qwen3.8-27b-nvfp4-2x-rtx5060ti-vllm-export.json` pulls the 3 runs into
    `output/` so they show up in any `statistics.sh` view alongside the llama.cpp rows; not yet
    run, so those rows aren't in `output/` yet. **Practical read**: llama-server + `qwen3.8:27b`
    single-GPU is still faster for one user (45 vs 32 tok/s) and more reliably reaches L6-full;
    vLLM's real win is concurrency. **Reading vLLM's per-task `tok_per_s` column**: vLLM's API
    has no prefill/decode split like llama.cpp's, so the harness divides generated tokens by
    total wall time — for coding tasks (short prompts) that's effectively decode speed, but for
    the `context_*` tasks (which emit ~15 tokens after a 7k-100k-token prompt) the same column
    is actually prefill speed in disguise: context_128k's "0.2 tok/s" is not a catastrophic
    decode collapse, it's 100,534 prompt tokens in 71.1s (~1,414 tok/s prefill). Don't read a low
    vLLM `ctx_*` tok/s figure as a decode regression without checking prompt_tokens/wall_s first.
  - Both picks trade "best documented capability at this VRAM size" for "most likely to actually
    load cleanly on the first try" — deliberately, since this plugin has never been exercised on
    this rig. Once either loads successfully, that's the point to branch out to a GDN-hybrid or
    MXFP4 model and see what actually happens.
- **MoE GGUF — patched vLLM** (2026-07-06, historical): `--quantization gguf` (ally's patched flag, not
  stock `--load-format gguf`) successfully loads Qwen3-Coder-30B-A3B MoE GGUF. Results:
  15/16 eligible tasks PASS at 31.2 tok/s (tp=1, single RTX 4090). python_hashmap TESTS_STILL_FAIL
  (base model gap — same as AWQ; see below). KV headroom caps at ~13760 tokens on single 24 GB
  due to GGUF loader workspace overhead (~5 GB); max_model_len=8192 is the practical ceiling.
  Speed: ~10% faster than AWQ tp=1 (28.5 tok/s) but 4× slower than llama-server (115 tok/s);
  gap is engine-level, not format. Harness uses `--quantization gguf` by default for GGUF mode;
  set `gguf_load_format=legacy` in model params to revert to `--load-format gguf` (legacy).
  Stock vLLM still fails with `Failed to map GGUF parameters: model.layers.X.mlp.experts.*` for
  any MoE / A3B model — the patch is required. Dense models (14B, 32B, 70B) work with stock vLLM.
- **vLLM single-request speed**: ~31 tok/s (GGUF tp=1) / ~28 tok/s (AWQ tp=1) vs llama-server
  ~115 tok/s for the same A3B MoE model — 4× engine-level gap confirmed on both GGUF and AWQ
  paths. tp=2 PCIe adds all-reduce overhead (16.6 tok/s). Crossover point: vLLM wins only at
  concurrent requests (continuous batching). For single-user coding workloads, llama-server is
  the clear choice. AWQ tp=1 is preferred over tp=2 on mismatched PCIe GPUs.
- **python_hashmap and vLLM**: TESTS_STILL_FAIL on AWQ (cpatonn standard base) and GGUF Q4_K_M
  (standard base). Confirms the PASS in qwen3-coder:30b-1m (llama-server) is specific to the 1M
  fine-tune checkpoint — not a GGUF/llama-server precision artifact. Do not apply f16 KV to
  paper over this; it is a base model capability gap.
- **Single-GPU 24 GB ceiling for 32B Q4_K_M**: `max_model_len=8192` with `enforce_eager` +
  `gpu_mem_util=0.94`. Thinking models (deepseek-r1, qwq) hit a 7 680-token effective output
  cap (`max_model_len − 512`) which exhausts the reasoning budget before `BEGIN_FILE` on L3+
  tasks (NO_BLOCKS). Same tasks pass on llama-server at `max_ctx=32768`.
- **Qwen3 thinking control**: `vllm_client.py` sends `chat_template_kwargs: {enable_thinking: think}`
  so vLLM behaviour matches llama-server for thinking/non-thinking variants. Non-Qwen3 models
  ignore this field silently.
- **HF-format mode (GPTQ/AWQ/safetensors)**: omit or set `gguf-file` to `-` in the `.vllm`
  model file; harness serves `hf_repo` directly without `--load-format gguf` or `--tokenizer`.
  Some GPTQ repos (e.g. AxisQuant/Qwen3.6-27b-gptq-int4) trigger vLLM's Mamba/SSM architecture
  handler for pure-transformer models, requiring `enforce_eager,max_num_seqs=1` to bypass CUDA
  graph Mamba-block allocation errors. AxisQuant GPTQ: 18/19 coding, 23 tok/s — worse than
  bartowski GGUF on llama-server (19/19, 36 tok/s) on both quality and speed. GPTQ INT4
  calibrated on C4 generic text fails `python_hashmap` (same `_EMPTY` omission as q8_0 KV).
  **AWQ preferred over GPTQ**: AWQ calibration is more representative than C4-calibrated GPTQ
  for coding tasks. Priority AWQ candidates: Qwen3.6-27B-AWQ (avoids Mamba/SSM config.json
  misdetection), Gemma4-26B-AWQ. Repo IDs to confirm before adding to model files.
- **FP8 KV cache**: param `kv_cache_dtype=fp8` → `--kv-cache-dtype fp8`. Halves KV memory,
  enabling longer contexts (e.g. deepseek-r1:32b 32k→64k on tp=2). **Caution**: verify
  `python_hashmap` does not regress — the task is precision-sensitive at KV boundaries. If it
  fails with fp8 KV, revert that model to `kv_cache_dtype=auto` (fp16 effective).
- **Prefix caching**: param `enable_prefix_caching` (bare boolean) → `--enable-prefix-caching`.
  Always enable for coding benchmarks — reduces TTFT on repeated system prompts. No quality impact.
- **Recommended baseline params for tp=2 coding workloads** (not yet tested on this bench):
  `tp=2,dtype=auto,kv_cache_dtype=fp8,enable_prefix_caching,gpu_mem_util=0.94,max_model_len=65536`
  Two notes from the 2026-09-17 single-card measurements: `max_num_seqs` can be set from the client
  count rather than hoarded (it costs ~0.5% of the KV pool, not the large fraction once assumed),
  and `gpu_mem_util=0.94` only works where nothing else holds the card — under WSL the display GPU
  loses ~1.1 GiB invisibly, which is why the 5060 Ti lane runs 0.92.
- **Concurrency strength — MEASURED 2026-09-17, no longer an open question.** vLLM's primary
  advantage over llama-server is multi-request scheduling, and `vllm bench serve` quantifies it
  (this build ships `vllm bench {serve,latency,throughput,sweep,startup}`; there is also a `BFCL`
  dataset that replays Berkeley Function-Calling traffic, untried here but the obvious next step for
  an agentic lane). On one RTX 5060 Ti with Qwen3.5-9B AWQ, 12k-token prompts, 256-token answers,
  cold prefix cache:
  | `--max-num-seqs` | concurrency | output tok/s | median TTFT | mean TPOT |
  |---|---|---|---|---|
  | 2 | 1 | 28.5 | 4.4 s | 17.8 ms |
  | 2 | 2 | 53.2 | 3.0 s | 24.1 ms |
  | 2 | 4 | 53.5 | 8.3 s | 25.5 ms |
  | 2 | 8 | 39.4 | 46.2 s | 33.3 ms |
  | 8 | 4 | 44.1 | 7.4 s | 59.6 ms |
  | 8 | 8 | 49.9 | 7.5 s | 119.2 ms |
  Aggregate throughput doubles from one client to two and then stops at the slot count; beyond it
  requests queue (at 2 slots and 8 clients, half wait 46 s for a first token and throughput *falls*).
  More slots remove the queue but split the GPU: per-stream decode goes ~30 -> ~8 tok/s at 8-way.
  Per-stream decode alone is ~56 tok/s; 12k-token prefill runs ~2,700 tok/s, which is why the
  concurrency-1 row reads 28.5 (4.4 s of prefill inside each request). Choose `--max-num-seqs` from
  the client count, not from VRAM — KV never binds here (8 x 12k = 96k against 209k available), and
  the flag itself costs only 0.5% of the pool. Real agent traffic is faster than this table because
  it hits the prefix cache 95% of the time; `--dataset-name random` never does.
  **Prompt length decides whether concurrency helps.** Same lane, 4 slots, replaying real
  tool-calling traffic (BFCL: `--dataset-name hf --dataset-path
  gorilla-llm/Berkeley-Function-Calling-Leaderboard`, ~450-token prompts, 24 requests, 2026-09-18):
  | concurrency | duration | output tok/s | median TTFT | mean TPOT |
  |---|---|---|---|---|
  | 1 | 77.3 s | 55.8 | 172 ms | 16.9 ms |
  | 4 | 24.7 s | **176.2** | 191 ms | 20.1 ms |
  **3.1x aggregate throughput with latency essentially unchanged** — the opposite of the 12k-prompt
  table above, where a fourth client only queued. Short prompts make prefill cheap, so the GPU
  spends its time decoding and genuinely parallelises; long prompts make prefill the bottleneck and
  extra clients wait. Agentic traffic is short *per tool call* but carries a large conversation
  prefix, so real sessions land between the two tables — which is exactly why prefix caching matters
  here. 24/24 requests succeeded, so real function schemas round-trip through the lane and its
  `qwen3_coder` parser cleanly; note vLLM's bench measures latency and throughput, NOT tool-call
  correctness (that needs BFCL's own scoring harness).
- **WSL2 mirrored-mode**: startup uses log-based readiness detection; inference uses LAN IP
  fallback. See `lib/vllm_client.py` `_wait_ready()` and `_detect_connect_url()`.

#### Model & Task Insights (accumulated findings)

- **Dense vs MoE on multi-step data tasks**: dense 27B consistently beats MoE 35B on
  `csv_nordic_property` and `node_csv_parser` — confirmed across two Qwen generations:
  - qwen3.5:27b (dense) PASS; qwen3.5:35b-A3B (MoE) FAIL csv_nordic
  - qwen3.6:27b (dense) PASS both; qwen3.6:35b-A3B (MoE) FAIL both
  Likely cause: MoE expert routing breaks multi-step analytical reasoning where context
  must be carried across sub-steps. Dense attention is more coherent here.
  Do NOT conclude a dense model is "better overall" — MoE is faster and often stronger
  on single-step coding tasks.

- **GGUF Q4_K_M on llama-server beats GPTQ INT4 on vLLM for 27B dense models**:
  qwen3.6:27b: bartowski GGUF → 19/19 @ 36 tok/s; AxisQuant GPTQ INT4 → 18/19 @ 23 tok/s.
  C4-calibrated GPTQ loses on both quality AND speed for this size class. The f16 KV
  requirement (see python_hashmap precision canary) applies to GGUF; GPTQ lands on the
  wrong side of the same precision boundary. When choosing between GPTQ and GGUF for a
  new 27B model, default to bartowski GGUF Q4_K_M on llama-server.

- **gpt-oss:20b non-determinism**: results vary 22–26/33 between identical compare.sh runs
  due to variable verbose reasoning length at temperature=0. Not a reliable benchmark
  subject. Known stable failure: context_64k retrieval bug (retrieves RC-5000 instead of
  correct value). Consider separating it from the canonical comparison set.

- **L6 from-scratch ceiling is 39/40**: test 33 (freefall crush on landing) has never been
  passed by any model. **Stub investigated 2026-05-29 — spec is NOT the problem.** The rule
  is explicit at `game.js` lines 45–46: "A freefall paratrooper landing on a landed paratrooper
  kills the landed one and decrements the appropriate landedLeft/landedRight counter."
  The test setup is unambiguous (same x=80, freefallRate=200, groundY=190 → lands in one tick).
  Root cause: models implement the standard landing routine (state→'landed', increment counter)
  but miss the secondary crush check in the same tick: scan landed paratroopers for proximity,
  kill the colliding one, decrement its counter. This is a **multi-effect landing event** —
  capability gap, not a spec gap. Do not change the test or the stub.

- **MTP spec decoding breaks benchmarks**: `--spec-type draft-mtp` (carnice, noctrex MTP
  variants) harms temp=0 determinism — confirmed regression on python_hashmap. Never add
  spec flags to benchmark runs. MTP layers in a GGUF (e.g. bartowski qwen3.6:27b b9180+)
  are harmless when spec flags are absent — the head loads but does not speculate.

- **noctrex MXFP4 is architecture-selective** (finding 2026-06-02): MXFP4 only improves results
  when the base quant has meaningful failures to fix. `noctrex-qwen3.6:35b` MXFP4 unlocked
  csv_nordic + node_csv_parser + L6 step 3 (25/29→31/33) because standard Q4_K_M failed those.
  `noctrex-qwen3-coder:30b` MXFP4 scored **29/33** (worse than qwen3-coder:30b-1m Q4_K_M 30/33)
  because the 1M variant already handles those tasks — nothing to unlock. Additionally,
  python_hashmap is **inconsistent**: passes in coding-only run but fails in full run — MXFP4
  precision for this architecture is right at the boundary, not reliably above it. Do not
  assume noctrex MXFP4 is a universal upgrade; check whether the base quant actually fails the
  precision-sensitive tasks first.

- **New model candidates (scout 2026-05-27 / 2026-06-02)**:
  - `Qwen3-Coder-Next` (Qwen/Qwen3-Coder-Next-GGUF) — BENCHMARKED 2026-05-28: **19/19 PERFECT**
    at 16.6 tok/s. ACTUAL SIZE: ~46 GB (4 shards: 15+14+14+3.3 GB) — ~72B dense; the "14.5 GB"
    estimate was shard 1 only. RAM-bound on 24 GB (52% VRAM). Not replacing qwen3-coder:30b-1m
    (9× faster at 150 tok/s). HIGH VALUE for dual-GPU: fully resident on 48 GB → ~35-40 tok/s.
    Added to default.vllm dual-GPU queue (commented).
    ⚠ HF repo (Qwen/Qwen3-Coder-Next-GGUF) GONE per 2026-06-02 scout — may have been renamed.
  - `gemma-4-31B` (unsloth/gemma-4-31B-it-GGUF, ~17.1 GB Q4_K_M) — BENCHMARKED 2026-05-28:
    **18/19**, 34.6 tok/s. FAILS node_csv_parser (ESM syntax: `export function` in CJS context —
    model output format bias, not capability gap). PASSES csv_nordic_property — confirms
    dense-beats-MoE pattern in Gemma 4 generation (gemma4:26b MoE fails csv_nordic at 110 tok/s).
    Peak skill L5 (passes dijkstra + hashmap); Skill L2 due to node_csv_parser L3 wall.
    Not added to default.txt (18/19 at ~35 tok/s doesn't displace any current model).
    ⚠ HF repo (unsloth/gemma-4-31B-it-GGUF) GONE per 2026-06-02 scout — file on disk.
  - `noctrex-qwen3-coder:30b` (noctrex/Qwen3-Coder-30B-A3B-Instruct-MXFP4_MOE-GGUF, 15.9 GB)
    — BENCHMARKED 2026-06-02: **29/33**, 58.9 tok/s avg, Skill L4. See MXFP4 note above.
    Not added to default.txt.
  - `Qwen3-Coder-480B-A35B` — 480B MoE, ~35B active, 36.6 GB Q4_K_M (lmstudio). Added to
    default.vllm dual-GPU queue (commented). Needs MoE GGUF fix first.
  - Devstral-Small-2507/2505 — OLDER versions (July/May 2025); current is 2512. Skip.
  - Devstral-2-123B (46.5 GB) — needs dual GPU; note for when hardware arrives.
  - Qwen3.6-27B-MTP (unsloth) — skip; MTP harms determinism (same as carnice pattern).
  - ⚠ Several unsloth gemma repos GONE per 2026-06-02 scout: unsloth/gemma-4-26B-A4B-it-GGUF
    (active default.txt entry — file must be on disk) and unsloth/Qwen3.6-35B-A3B-GGUF
    (experimental only). All flagged with comments in model config files.

- **New model candidates (scout 2026-06-07)**:
  - `qwen3-coder:30b-480d` (mradermacher i1 Q4_K_M, 480B distill) — BENCHMARKED 2026-06-07:
    **29/33**, 51.5 tok/s, Skill L4. python_hashmap FAILS in full run (passes in coding-only run).
    mradermacher i1 imatrix has the same precision boundary failure as noctrex MXFP4 at 30B A3B.
    NOT added to default.txt. Pattern confirmed: for 30B A3B, only unsloth standard Q4_K_M
    reliably passes python_hashmap in full-run context.
  - `mellum2:12b` (JetBrains, MXFP4_MOE, 6.5 GB) — BENCHMARKED 2026-06-07: **23/33**,
    144.5 tok/s avg, Skill \<L1, Peak L4. Architecture 'mellum' requires llama.cpp ≥ commit
    4fb16eccc (PR #23966, "model: add Mellum architecture"). python_hashmap PASSES — MXFP4
    precision holds at 12B A2.5B (unlike 30B A3B where it fails). Failures: csv_nordic_property,
    node_csv_parser (MoE data ceiling), context_64k TESTS_STILL_FAIL (hard retrieval limit),
    context_128k NO_BLOCKS, multihop both FAIL (12B cannot do 2-hop retrieval at 30k+ context).
    Ties qwen2.5-coder:14b at 23/33 but at 2.1× the speed. NOT added to default.txt.
  - `mellum2:12b-think` (JetBrains thinking variant, 7.0 GB) — BENCHMARKED 2026-06-08:
    **21/33**, 143.5 tok/s. Worse than instruct: thinking regressions (-6) outweigh gains (+4).
    Gains: node_csv_parser, node_para_combat, multihop_forward, multihop_reverse.
    Regressions: node_slugify, python_multifile_rename, node_memoize_bug, node_debounce,
    python_dijkstra, python_hashmap (reasoning tokens exhaust budget before _EMPTY = None).
    Instruct is the better general-purpose variant; thinking only useful if multihop is priority.
  - ⚠ Additional GONE repos per 2026-06-07 scout: noctrex/Qwen3.6-35B-A3B-MTP-MXFP4_MOE-GGUF
    (default.txt entry) and unsloth/Qwen3-Coder-30B-A3B-Instruct-1M-GGUF (default.txt entry).
    Both files must be on disk. All four default.txt GONE entries flagged with ⚠ comments.
#### Extended Model Investigations (qwen3.8-flash-next rebuild history, forks, tiel-coder)

  - **qwen3.8-flash-next** (Qwen's Qwen4-preview architecture, official release 2026-08-26,
    ~106 GB unsloth UD-Q4_K_XL, 4-part): new architecture entirely — Gated DeltaNet + Qwen Sparse
    Attention (QSA) hybrid, Gated Residual, N-gram Embedding (125B main + 51B n-gram embedding +
    4B MTP, 6B activated/token). **Requires a separate llama-server build** — mainline llama.cpp
    (the binary this repo normally uses) does NOT support this architecture; built from
    `unslothai/llama.cpp` @ branch `qwen4exp/qwen3.8-flash-next` (commit `eaf9376`, `0.3.0-dev`)
    at `~/GIT/llama.cpp-qwen4exp`, invoked via `LLAMA_SERVER_BIN=~/GIT/llama.cpp-qwen4exp/build/bin/llama-server`
    (bench.py already honors this env var — no code change needed for that part).
    **Launch config gotcha**: use `--fit on --fit-target 4096` ONLY — both `--n-gpu-layers` and
    `--tensor-split` conflict with `--fit`'s own auto-placement and cause it to abort fitting,
    falling back to a naive single-GPU placement that OOMs. `--fit` correctly auto-distributes
    across all 3 GPUs on its own once those two flags are removed (confirmed 2026-08-28).
    **10-task spot check CONFIRMED 2026-08-29: 9/10 PASS**, but only once given adequate time —
    default per-task timeouts (300-600s) are far too short for this model's default
    `reasoning_effort=xhigh` at its steady-state ~4-7 tok/s on this hardware. First pass at
    default timeouts showed 5 tasks FAIL(TOOL_ERROR) at exactly 0.0 tok/s landing right on the
    timeout boundary — root cause confirmed by reading `llama_server_client.py`: the harness
    sends non-streaming requests (`"stream": false`), so a slow-but-working response is
    indistinguishable from a hang. Retested all 5 at `model_timeout=2400` — all passed, several
    within even the old default, confirming genuine speed/timeout issue, not capability. Only
    real failure: `node_csv_parser` (NO_BLOCKS, format compliance). Includes a `python_hashmap`
    (L5 precision canary) PASS and a `node_paratrooper` (L6-full) PASS — the latter NOT
    independently re-verified given how often single passes on that exact task have failed
    repeat verification this cycle (see qwen3.8:27b/ornith:1.5-35b entries) — treat as promising,
    not confirmed.
    **OPTIMIZATION CONFIRMED 2026-08-29**: `reasoning_effort` wiring was skipped — response
    metrics showed gen_tok counts matching direct task output sizes exactly, i.e. no visible
    reasoning overhead at default settings, so effort-level tuning wasn't expected to help. The
    real finding: `gpu_snapshots` showed only ~60/72 GB VRAM used after load (13.7 GB idle
    despite `fit_target=4096`) and 93% GPU util / 12% mem-bandwidth util during generation — a
    compute-bound signature pointing at unoptimized/early CUDA kernels for the new architecture's
    novel components (QSA indexer, N-gram embedding gather, Gated Residual) in this 2-day-old
    branch, not a placement issue. Tested `fit_target=512` + `batch_size=1024`/`ubatch_size=512`
    (the field report's own values) together: 6-14x speedup on short generations (<100 tokens,
    dominated by fixed per-request overhead) shrinking to a modest 1.2-1.8x on medium/long
    generations, collapsing to noise-level (~1.2x, decode speed literally unchanged at 4.1 tok/s)
    on the single longest task (`node_paratrooper`). Confirms the config change cuts fixed
    overhead, not the actual sustained decode ceiling — a likely kernel-level limit not reachable
    by further flag tuning. Capability held at 9/10 either way. **Promoted this config to primary**
    — strictly faster, zero downside. Further gains likely need upstream kernel work, not more
    config sweeping. Full per-task before/after numbers in `models/candidates.txt`.
    **Unplanned incident**: an unexplained hard PC crash occurred during this sweep (see
    `hw-upgrade-july-2026.md`) — not confirmed caused by this testing, but prompted tightening
    GPU power limits (300/280/280W → 260/240/240W) and adding an automatic pre-flight power-limit
    check to `run.sh` for any 3+ GPU run (see Repository Layout below). All testing after that
    point re-enabled `hwmonitor` and completed cleanly (max 66°C, zero WARN/CRIT).
    **MAINLINE BINARY UPDATE 2026-08-29**: mainline `ggml-org/llama.cpp` merged native qwen4exp
    support (PR #27742) plus the exact graph-split optimization this model needed (PR #27880) and
    several other qwen4exp-specific fixes — the separate unsloth fork is no longer strictly
    required. CONFIRMED performance comparison (fork v2 vs mainline commit c841aeeb8, same
    config, same tasks): NOT a clear speedup, mixed result (one task comparable, one identical,
    one notably slower on mainline) — the graph-split fix likely targets the same fixed-overhead
    class our `fit_target`/batch tuning already captured. **Recommend switching to mainline
    anyway** (`LLAMA_SERVER_BIN=~/GIT/llama.cpp/build/bin/llama-server`, the repo's normal binary
    location) — not for speed, but because it's actively maintained going forward versus a frozen
    fork commit. Fork remains a documented fallback. Full comparison in `models/candidates.txt`.
    **REBUILD CONFIRMED 2026-09-03** at commit `67a17c17c` (~1 month of accumulated qwen4exp
    fixes since `c841aeeb8`, including `b356fa262` — a kv-cells lookup optimization whose own
    commit message reports +4.9% tg measured directly on Qwen3.8-Flash-Next UD-Q4_K_XL — and a
    model-agnostic CUDA MoE fusion). Re-ran the same 3-task comparison: **real, large speedup** —
    `python_hashmap` 6.1→23.0 tok/s (~3.7x), `python_expr_eval` 4.1-6.2→23.2 tok/s (~4-5.7x).
    `python_safe_div` went ~27-32→~19-24 tok/s (~25-30% slower, verified across 6 repeat runs —
    real, not noise). Pattern: all three tasks now converge to roughly the same ~19-23 tok/s
    sustained rate, where before they were wildly split — consistent with the accumulated fixes
    genuinely repairing the per-token decode degradation the earlier optimization sweep diagnosed.
    Net effect for real coding work (hundreds-to-thousands of tokens, not tens): strongly
    positive. **Current recommendation (SUPERSEDED BELOW): rebuild mainline periodically** — this
    architecture is under active upstream development and these gains came from ~1 month of
    accumulated commits. Full detail in `next-runs.md` and `models/candidates.txt`.
    **⚠ REGRESSION CONFIRMED 2026-09-04** at commit `49c0dc82b` (82 commits past `67a17c17c`) —
    rebuilt specifically to test a new multi-GPU CUDA-graph lever (`0ba6499c3`, gated behind
    build flag `-DGGML_CUDA_GRAPHS=ON`, added to `llamacpp/build-llama.sh`, plus runtime env var
    `GGML_CUDA_GRAPH_OPT=1`). Result: **not a win, a clear regression on both counts**.
    `node_paratrooper`: ~22-24 tok/s (67a17c17c) → 13.8 tok/s (49c0dc82b, no graphopt) → 11.3
    tok/s (WITH `GGML_CUDA_GRAPH_OPT=1` — the new lever makes it worse, not better, for this
    3-GPU `--fit` topology). Capability held: PASS both runs (8/8 total confirmed passes for
    this model). `python_hashmap` 23.0→10.3 tok/s (-55%), `python_expr_eval` 23.2→16.9 tok/s
    (-27%), `python_safe_div` ~19-24→31.4 tok/s (the one task that got faster) — same
    short-task-up/long-task-down split as the 67a17c17c improvement, but inverted. Not bisected.
    **"Rebuild periodically" is NOT a one-way ratchet — verify the 3-task speed comparison after
    every rebuild before switching. Current recommendation: pin to commit `67a17c17c` for
    production use of this model; do not enable `GGML_CUDA_GRAPH_OPT=1` for it.** Full detail in
    `next-runs.md` and `models/candidates.txt`.
    **⚠ SECOND, WORSE REGRESSION CONFIRMED 2026-09-25** at commit `d81aef199` (395 commits past
    `67a17c17c`, current `origin/master` as of that date). Rebuilt as part of a routine "verify
    before trusting" check, not chasing a specific lever this time. `python_hashmap`:
    23.0 → **4.4 tok/s (-81%)**. `python_expr_eval`: 23.2 → **4.8 tok/s (-79%)**. `python_safe_div`:
    ~19-24 → 15.5 tok/s (roughly in range, the short task again least affected — same pattern as
    both prior rebuilds). Capability held (all 3 still PASS). This is a substantially worse
    regression than the 2026-09-04 one (-55%/-27%) on the same two tasks — whatever degraded the
    per-token decode rate for this architecture has gotten worse over these 395 commits, not
    better, not bisected. **The pin to `67a17c17c` is reaffirmed, more strongly than before** —
    two independent later commits, 82 and 395 commits out respectively, have both regressed this
    model, zero rebuilds since the pin have improved on it. Rebuilt back to `67a17c17c` afterward
    to restore the correct production binary on this rig (do not leave `origin/master` checked
    out for this model's use). A same-day spot check of `gemma4:26b-qat` on the regressed
    `d81aef199` build also showed a real, if smaller, slowdown (~110 vs the documented ~129 tok/s
    baseline) despite a commit in that range (`c350a40bb`) specifically targeting that model's
    flash-attention shape — possibly a broader regression in this commit range, not isolated to
    qwen4exp, though only one data point so far outside the qwen3.8-flash-next 3-task comparison.
    **⚠ THIRD REGRESSION CONFIRMED 2026-10-03** at commit `bed0a8566` (608 commits past the pin).
    Unlike the first two attempts, this one was NOT a routine check — a specific cluster of
    qwen4exp commits landed since the pin that looked genuinely promising: MTP support
    (`c061df198`), a re-enabled `-sm tensor` true-tensor-split mode (`10f340d1a`, previously
    crashing for this architecture per `#27941`), and the long-flagged GDN L2-norm correctness
    fix (`5fdfa6282`, known since 2026-09-07). Rebuilt, then ran the fullest verification yet: the
    3-task speed check, 3× `node_paratrooper` for determinism, and — for the first time ever on
    this rig — the full 3×24GB context group. **Speed: python_hashmap 23.0→8.16 tok/s (−64.5%),
    python_expr_eval 23.2→6.38 tok/s (−72.5%), python_safe_div ~19-24→30.47 tok/s (faster, the
    short task is spared again — third rebuild in a row showing this exact pattern).**
    **Capability: node_paratrooper FAILS 3/3, deterministically** — `eval_count=5311` identical on
    every run, ruling out flakiness; this is worse than either prior regression, which both held
    PASS while only losing speed. First time a rebuild for this model has cost an actual confirmed
    capability, not just throughput. **New data point from the same session: the 3×24GB context
    group, run for the first time ever, PASSED all 6 tiers including context_256k (8.13 tok/s)**
    — a real answer to the "can this model exceed gpt-oss:120b's hard 131072 ceiling" question,
    and the answer is yes — but this was measured on the regressed binary's degraded decode path,
    so the capability (reaches 256k) is trustworthy while the speed number is not; re-run on
    67a17c17c for a representative number before citing it anywhere. `context_64k` TOOL_ERROR'd on
    the first attempt (timeout, consistent with the slowdown) but PASSED on an immediate retry at
    4.7 tok/s — not evidence of flakiness beyond the timeout margin being too tight for this
    binary's speed. **Reverted back to the `67a17c17c` pin the same day.** Tally: three independent
    later commits (82, 395, and 608 commits past the pin respectively) have now regressed this
    model; zero rebuilds since the original pin have improved it, and this is the first to cost a
    capability outright. The pin stands, more firmly than ever — do not attempt another rebuild of
    this model without a specific, strong reason, and always run the full 3-part verification (not
    just the 3-task speed check) before trusting any future rebuild.
    **TRACK C — SPEED REGRESSION BISECTED, CONFIRMED 2026-10-03.** The qwen4exp-heavy commit
    cluster found 2026-10-02 looked promising enough to justify root-causing the speed regression
    rather than just re-pinning again. Observation that shaped the approach: the 3 regressions
    looked like TWO separate bugs, not one — the speed drop was already present at `49c0dc82b`
    (close to the pin) and stayed present at `bed0a8566` (far from the pin), while the
    `node_paratrooper` capability loss was absent at `d81aef199` (between the two) and only
    appeared at `bed0a8566` — so bisected each separately rather than the full 608-commit span.
    **Phase 1 (speed regression, `67a17c17c` good → `49c0dc82b` bad): bisected to completion in 5
    rebuild+test cycles** (`git bisect`, 3-task speed check per step — every single step came back
    bad, meaning the regression sits almost immediately after the pin, not spread through the
    range; confirmed via `git rev-list --count` that `49c0dc82b` is actually only 35 commits past
    the pin in the real commit graph, not the "82" figure used elsewhere, which was computed some
    other way). **Culprit: commit `c61b98b875` ("model: add NVIDIA Nemotron-3-Puzzle-75B-A9B
    (NemotronHPuzzle) support", #25444, 2026-09-03).** This PR added per-layer MoE expert-count
    support (`n_ff_exp(il)`/`n_expert_used(il)` accessors) for Nemotron-3-Puzzle's heterogeneous
    per-layer expert routing. The change that hits every MoE architecture, confirmed by direct
    diff inspection of `src/llama-graph.cpp`'s `build_moe_ffn` (the per-decode-step expert-
    aggregation loop every MoE model runs): `hparams.n_expert_used` (a plain scalar field read)
    became `hparams.n_expert_used(il)` (a function-call accessor), plus the same change in
    `llm_graph_context`'s constructor (`n_expert_used(cparams.warmup ? hparams.n_expert :
    hparams.n_expert_used())`). For qwen4exp (uniform expert count, no actual per-layer variation
    needed) this is value-equivalent but demonstrably not performance-equivalent — qwen4exp.cpp's
    own diff only touches load-time `n_ff_exp` reads (once per model load, not the issue); the real
    cost is the shared `build_moe_ffn` hot path every decode step runs through. **Root cause
    located, not fully explained**: why a function-call/array-indexing change costs 3-4× decode
    throughput (vs. a scalar field read) would need actual GGML-graph profiling, which a bisection
    can't establish on its own — reporting the confirmed commit and mechanism location, not an
    overclaimed full performance diagnosis. **Phase 2 (capability regression, `d81aef199` good →
    `bed0a8566` bad, ~213-commit range) was NOT attempted** — Phase 1 alone took ~4 hours of real
    wall-clock (5 rebuild+test cycles); Phase 2's test (`node_paratrooper` itself, ~20-25 min/step
    given the regressed decode speed in that range) is comparably expensive, and stopping after a
    clean Phase 1 result was the right call rather than pushing into an equally costly second
    investigation without a fresh decision to do so. hwmonitor: no WARN/CRIT across all 5 steps
    (max 44-64°C). Repo and binary verified restored to the `67a17c17c` pin afterward (build 364).
    **Practical implication: this is confirmed to be ONE bug causing the speed drop in all three
    rebuild attempts, not three unrelated regressions** — but it does not explain the separate,
    later-introduced `node_paratrooper` capability loss, which remains unexplained pending a
    possible future Phase 2. Full bisection trail (every commit tested, its classification, and
    the position-halving verification) in `next-runs.md`.
    **ATTEMPTED FIX, 2026-10-03/04 — CLOSED without success: "pin stands, root cause narrowed
    but not found."** User requested checking whether any of llama.cpp's then-861 remote branches
    already fixed this — none did; the only commit that has ever touched the regressed code
    (`n_expert_used_il` in `build_moe_ffn`) is the culprit itself. Branched `fix/qwen4exp-moe-perf`
    off `origin/master` @ `836d5717` to attempt an actual fix rather than just re-pinning.
    **A straight `git revert c61b98b875` conflicts in 6 files** (`llama-hparams.cpp/.h`,
    `llama-model-loader.cpp`, `llama-model.cpp`, `models/bailingmoe3.cpp`, `models/nemotron-h.cpp`)
    — too many newer architectures (qwen3next, qwen35moe, cohere2moe, deepseek2ocr, exaone-moe,
    kimi-linear, laguna, llama4, mellum, mimo2, minimax-m2/m3, openai-moe, step35) were migrated
    onto the per-layer array infrastructure this commit introduced; a full revert would break all
    of them. **Not viable.**
    Pursued a narrow, targeted fix instead: patched the two `build_moe_ffn`/`llm_graph_context`
    call sites to read `hparams.n_expert_used_arr[il]` directly instead of calling
    `hparams.n_expert_used(il)` (the out-of-line accessor), on the theory that a cross-translation-
    -unit function call was the cost. **Built and tested — DID NOT HELP**: python_hashmap 6.22
    tok/s, python_expr_eval 4.95 tok/s (no better than, arguably slightly worse than, the
    already-regressed `bed0a8566` baseline of 8.16/6.38). Hypothesis empirically disproven.
    **Systematic file-by-file isolation of the remaining 56-file commit, by source analysis
    (not blind rebuilds) given the first empirical test's cost:**
    - `llama-model.cpp` (51 lines, the largest remaining change) — every hunk is either load-time-
      only (`load_hparams`/`load_tensors`/`print_info`, run once at model load) or inside
      `llama_meta_device_get_split_state` (the `LLAMA_SPLIT_MODE_TENSOR`/meta-device callback) —
      confirmed **structurally unreachable** for this model: `common/fit.cpp` throws if
      `split_mode == LLAMA_SPLIT_MODE_TENSOR`, and qwen3.8-flash-next always runs via `--fit`.
      Ruled out without a rebuild.
    - `llama-model-loader.cpp`, `llama-model-saver.cpp` — a one-time backend-buffer-type
      capability probe at load, and model-export/save code (never runs during serving),
      respectively. Ruled out without a rebuild.
    - `models/nemotron-h.cpp`, `models/bailingmoe3.cpp` — different architectures entirely, not
      in qwen4exp's dispatch path.
    - `llama-hparams.h`/`.cpp` (the struct + accessor definitions) — **measured the actual struct
      growth precisely** (compiled a standalone `sizeof()` probe against both the pin's and
      current master's header): `llama_hparams` grew from **31,968 → 36,104 bytes (+4,136 bytes
      exactly)**, confirming the two new 512-entry `uint32_t` arrays, not an estimate. Traced
      where this struct is actually copied by value for qwen4exp (several `llm_graph_input_*`
      classes store `const llama_hparams hparams;` by value, not by reference) and found the one
      relevant copy (`llm_graph_input_mem_hybrid`, via `build_inp_mem_hybrid()`) happens **at most
      once per decode step**, and that object has its own `can_reuse()` caching mechanism
      (untouched by the regression) that often avoids even that. A handful of KB copied
      occasionally cannot plausibly explain a 3-4× throughput regression — **magnitude argument
      against this hypothesis**, not tested via rebuild since the mechanism itself doesn't support
      it strongly enough to justify another ~40-minute cycle.
    **Conclusion, investigation CLOSED 2026-10-04**: every concrete, source-readable hypothesis
    has been either empirically disproven (accessor call) or ruled out by magnitude/reachability
    analysis (struct copy cost, meta-device path, load-time-only files). The actual mechanism is
    most likely GPU-side (CUDA kernel dispatch/scheduling), which cannot be determined by reading
    source — it needs real profiling (`nsys`/`ncu` or `perf`), none of which are installed on this
    rig, and installing them would need `sudo` (not done, a bigger ask left for later if ever
    revisited). **"Pin stands, root cause narrowed but not found."** The `fix/qwen4exp-moe-perf`
    branch (one commit, `78646146f`, the disproven accessor-inlining patch) is kept locally in
    `~/GIT/llama.cpp` for reference — not merged, not used, repo restored to the `67a17c17c` pin.
  - **DeepSeek-V4.1-Flash via the JigSawPT `dsv41-porte` llama.cpp fork** (552B total params,
    40 layers, 384 routed experts, 189 GiB engram tables; `~/GIT/deepseek-v41-flash-on-5090`
    technical report + `~/GIT/llama.cpp-dsv41` fork clone, tested 2026-10-06/07): a third,
    separate fork from `ds4`/DwarfStar and from mainline — `--moe-stream` streams routed experts
    from NVMe through a VRAM cache + a pinned-RAM "L2" tier. Goal was explicitly "biggest model
    possible," not speed. **Build/download/load all succeeded** despite the fork's own README
    saying "Linux builds are untested... nobody has run them" — clean compile on the first try,
    all 502 GB/11 shards downloaded and byte-verified exact against the HF repo's own metadata
    (hit and fixed one real snag: 2 of the 11 shards needed `hf_xet` installed, the opposite
    problem from the usual "disable Xet" lesson — check the actual error before assuming either
    default). Loaded on a single free 24 GB card (`--moe-stream-cache 18 --moe-stream-l2 32`,
    `-c 32768`) — the single biggest model ever run on this rig.
    **`node_para_core` (L6 step 1, exported via `bench.py --export-task` and sent to the running
    server by hand): PASS, 7/7 tests, on both the 3090 and the 4090**, with byte-identical
    generated code (same MD5) across both — genuine determinism confirmed. 3090: 46m8s (0.69
    tok/s decode). 4090: 33m6s (0.93 tok/s decode) once correctly rebuilt — the first attempt on
    the 4090 used a binary still compiled with `-DCMAKE_CUDA_ARCHITECTURES=86` (Ampere-only),
    forcing PTX JIT fallback on the 4090's `sm_89` and making the "faster" card appear to hang
    (didn't finish in 60 min) — a pure build-targeting artifact. **Lesson: always confirm
    `CMAKE_CUDA_ARCHITECTURES` in `build/CMakeCache.txt` matches the GPU under test before
    trusting any cross-GPU timing on this fork.**
    **`node_paratrooper` (L6-full) was attempted on the (correctly-built) 4090 and abandoned
    after ~8.8 hours — a genuine, valuable negative result, not a model failure.** Streamed via
    SSE to watch tokens arrive live rather than waiting blind: the first ~35 min produced
    completely coherent code (correct restated-spec comments, into `getResult()`/`getState()`),
    but decode throughput collapsed roughly 15x as generation got longer (~90 tokens in 35 min
    vs. only ~1,350 tokens after 7h13min) — independently reproducing, with real numbers on this
    hardware, the original report's own finding that the working set (and disk-miss rate) grows
    with generation length, which a 32 GiB L2 cache (vs. the report's own 72 GiB) can't keep up
    with. **Headline capability ceiling for this rig: short-to-medium tasks (hundreds to ~1,200
    tokens) are practically completable; full from-scratch L6-scale generations are not, at this
    VRAM/RAM tier.** Separately, `--moe-stream-direct` (O_DIRECT) measured **slower** than the
    buffered path here (0.98 vs 1.6 tok/s on a short test) — opposite of the report's own
    native-Windows result, plausibly because WSL2's ext4 root is itself a vhdx on NTFS, so
    bypassing the Linux page cache doesn't remove a layer of virtualization the way it does on
    bare metal; one data point, treat as provisional.
    **Follow-up, 2026-10-08 — two cheap/short tasks, both clean PASS, confirming the capability
    ceiling is about task SIZE, not whether the model can reason or code correctly.**
    `multihop_chain_5` (L4, genuine 5-hop config-inheritance reasoning, tiny ~3.5 KB prompt,
    single-number answer): **PASS**, correct answer `90` (avoided both the sibling distractor
    `45` and the top-level distractor `30`) — confirmed via the task's own pytest. Just **7m25s
    total**, by far the fastest completion in this whole investigation — 918 prompt tokens @
    2.14 tok/s prefill, only 10 completion tokens. `python_hashmap` (L5, this benchmark's own
    signature precision canary): **PASS, 11/11 tests**, including the precision-boundary test
    the canary exists to catch — correctly emitted the module-level `_EMPTY = None` that models
    omit under precision stress. **First time this canary has been checked against a model
    that's low-precision at the architecture level (native fp8/MXFP4), not just KV-cache
    format — it holds clean**, same pattern as `qwen3.5:27b`/`qwen2.5-coder:32b-q4` with q8_0
    KV. 21m11s total; decode rate (0.94 tok/s) matches `node_para_core`'s own 0.93 tok/s on this
    same GPU almost exactly, confirming ~0.9-1.0 tok/s is this hardware's genuine short-task
    decode ceiling for this model, not noise. Full detail, every command, and every number:
    `memory/project_deepseek_v41_flash_poc_plan.md`.
  - **llama.cpp-adaptive-kv-streaming fork** (`RaymondHuang210129/llama.cpp-adaptive-kv-streaming`,
    investigated 2026-09-01/02): adds `--kv-stream-stage-mib` to `llama-server`, streaming the KV
    cache between pinned host memory and a bounded CUDA pool for long contexts on GPUs too small
    to hold the full KV cache — targets `qwen3.8:27b` specifically (not `qwen3.8-flash-next`; the
    fork predates the qwen4exp merge entirely). Author validated on an RTX 5070 Ti (Blackwell,
    compute capability 12.0). **Crashes reliably on this rig's Ada/Ampere GPUs** the moment
    streaming is engaged — cleanly isolated across 3 controlled runs (2 different KV cache types
    both crashed in 2 different CUDA kernels only when streaming was active; the identical
    non-streaming config worked cleanly). Not pursued further on this hardware; revisit only if a
    Blackwell-generation GPU is added to the rig. A self-contained repro/test script for that
    scenario is saved at `test-adaptive-kv-streaming-blackwell.sh` (repo root) for whenever that
    hardware is available. Full isolation detail in `next-runs.md`;
    memory: `project_adaptive_kv_streaming_fork`.
  - **ik_llama.cpp fork with MTP speculative decoding** (RESULTS 2026-09-04): dedicated qwen4exp
    support plus MTP (NextN) self-speculative decoding for `qwen3.8-flash-next`
    (`qwen3.8-flash-next-ikllama` in `candidates.txt` — note this fork's `--fit` is a bare boolean,
    `fit=on` errors). Needed a separate small "predictor-only" MTP companion GGUF via `-md`
    (unsloth's standard file has no embedded MTP tail); getting that to fit alongside `--fit`'s
    main-model placement on this 3-GPU topology was fragile — `--fit-margin` and `-ngld 0` had no
    effect, only reducing `--ctx-size` to 2048 actually freed enough VRAM. **MTP spec-decoding
    genuinely works** (92.6% draft acceptance rate) but effective throughput was only ~17.1 tok/s
    — slower than mainline's current tuned baseline (~19-24 tok/s, no speculation needed). This
    fork also doesn't honor `enable_thinking:false` for this model (genuine `<think>` reasoning by
    default), making its baseline handicapped versus mainline's zero-reasoning behavior. **Not
    currently a win on this hardware** — the reported ~90 tok/s on a single RTX 5090 elsewhere
    likely reflects Blackwell's bandwidth + no cross-GPU overhead, not reproduced on this 3-way
    Ada/Ampere split.
    **Follow-up (2026-09-04), qwen3.8:27b-GSQ-RCO with an embedded MTP head** (official repo
    ships `-mtp` variants — one file, no separate `-md`/VRAM-fitting fragility): loaded cleanly,
    single GPU. 90.8% draft acceptance rate again, but effective speed (55.52 tok/s) was
    statistically identical to this quant's already-confirmed non-speculative baseline
    (54.9-56.9 tok/s) — zero net gain. **Two data points now show MTP's payoff depends on
    whether the baseline has spare decode headroom to exploit, not on acceptance rate alone** —
    qwen3.8-flash-next's slow/compute-bound baseline saw a real 2.2x gain (still not enough to
    beat mainline); this already-fast, likely bandwidth-saturated baseline saw none. Check
    baseline headroom before expecting a win from MTP on any future test. Full diagnostic detail
    in `next-runs.md`; memory: `feedback_mtp_spec_decoding_lessons`.
    **Reddit tip (2026-09-14), now CONFIRMED (result below)**: a Reddit tip — "stream ngrams off ssd and offload experts
    to cpu" on ≥16 GB VRAM + 64-96 GB RAM — checked against `~/GIT/llama.cpp/src/models/
    qwen4exp.cpp` and confirmed to map to two real mechanisms, not folk wisdom: the huge N-gram
    Embedding table (`per_layer_token_embd` tensor) is created with `TENSOR_READ_LAZY` (rows
    paged from the mmap'd GGUF on demand, requires mmap enabled — already true for this repo's
    config), and "offload experts" is the existing `-ngl 999 --n-cpu-moe N --no-repack` CPU-MoE
    paging technique documented below. Recipe: skip `--fit`, restrict via `CUDA_VISIBLE_DEVICES`
    to match a ≤32 GB VRAM budget, use `-ngl 999 --n-cpu-moe N` explicitly. `N` and resulting
    speed are both genuinely unknown — this ~106 GB model vs. a 16-32 GB VRAM target is a much
    bigger gap than the "~30% of MoE layers per 3 GB overage" rule learned from `gpt-oss-120b`.
    Both this rig (96 GB RAM) and a separate RTX 5060 Ti ×2 box (96 GB DRAM) qualify to try this.
    Full detail in `next-runs.md`; playbook in `how-to-vllm.md` §6.
    **RESULT, CONFIRMED 2026-09-14/15** on 1× RTX 5060 Ti 16 GB (Blackwell) + Ryzen 7 9800X3D, WSL2
    memory=88GB, model on WSL ext4 (`qwen3.8-flash-next-16gb` in candidates.txt): full run
    **37/38 eligible at 18.1 tok/s avg** (1:21:43). Coding 18/19 (only node_csv_parser, the same
    missing-END_FILE format failure as the 3×24 GB rig), web 4/4, L6 stepped 4/4 plus
    node_paratrooper, context 8k-128k 5/5 (128k: 966s at 11.8 tok/s), multihop 5/5.
    context_256k is SKIPPED_VRAM by its own min_vram_gb=48 guard (lib/tasks.py:707).
    **The working recipe differs from the one above**: KEEP `--fit on --fit-target 512` (at
    67a17c17c `--fit` moves MoE experts to CPU by itself, common/fit.cpp:522, so no hand-tuned N)
    and ADD `--no-repack` (without it, CPU-side experts are copied into anonymous RAM and can't be
    re-read from NVMe). Never `--no-mmap`/`--mlock`. The GPU averaged 43 W at 34% util, so decode
    is CPU/RAM-bound. NVMe reads fell from 240-900 MB/s cold to ~30 MB/s once the hot experts sat
    in page cache (~75 GB). **Pitfall: model files on `/mnt/c` (WSL 9p) loaded at ~190 MB/s. Move
    them onto WSL's ext4 first** (the load then took 1m24s). Steps: `how-to-test-flash-next.md`.
  - **tiel-coder:35b** (peculiar-ragdoll, Tiel-Coder-35B-A3B, UD-IQ4_XS, ~16.5 GB, single RTX
    4090, no Ampere+ required, f16 KV): coding-focused Ornith derivative, found via scout
    2026-09-05 — flagged by an external community thread as "Ornith on steroids for coding"
    (9+ independent re-uploads appeared across one scout cycle, a strong trending signal).
    CONFIRMED 2026-09-05 **10-task spot check: 8/10 at ~165 tok/s** — fastest model in this
    VRAM tier (faster than qwopus3.6:35b's 161 and ornith:1.5-35b's 155 tok/s). PASSES
    `python_hashmap` (L5 precision canary) and `csv_nordic_property` — two of the harder
    discriminators in the whole benchmark. FAILS `node_slugify` (L2, TESTS_STILL_FAIL — a
    genuine wrong-output bug, not a format/parsing issue) and `node_paratrooper` (L6-full,
    expected universal wall). **PROMOTED to full 19-task coding run: 18/19 at 163.9 tok/s avg,
    81.2s total** — only `node_slugify` fails; also passes `python_dijkstra` (L5) and every
    other L3 CSV task (`node_csv_parser`, `awk_csv_stats`, `java_word_freq`). Stronger L5
    coverage than `qwen3-coder-rtpurbo:30b` (which fails hashmap) at a comparable coding score
    and speed tier. GPU temps healthy (max 60°C). Added to `models/24gb.txt`.
    **CONFIRMED 2026-09-05 web + L6-stepped (single RTX 4090, --num-ctx 32768)**: **WEB: 4/4
    PASS at ~161 tok/s** — python_config_loader, bash_preflight, node_express_validation,
    python_fastapi_endpoint. Notable: this is a coder fine-tune, and the established rule is
    that post-trained coder fine-tunes FAIL fastapi (qwen3-coder:30b-1m, rtpurbo, qwopus3.6:35b
    all fail it) — tiel-coder:35b is a genuine exception. **L6 STEPPED: 3/4** — node_para_core
    PASS (167.0 tok/s), node_para_turret PASS (164.7 tok/s), node_para_entities **FAIL**
    (TESTS_STILL_FAIL, 161.4 tok/s, 19.4s — clean capability failure at ctx=32768, not a
    context/budget issue), node_para_combat PASS (158.9 tok/s — passes because the step-4
    scaffold provides a reference entities implementation, same pattern as equinox:31b). Does
    NOT complete the full L6 stepped chain — not a 15th completer. GPU temps healthy (max 62°C).
    **CONFIRMED 2026-09-05 context + multihop (single RTX 4090)**: **CONTEXT: 6/6 PASS 8k-256k,
    including 256k on a single GPU** — ctx_8k *100.4 (4.4s), ctx_16k *102.0 (7.4s), ctx_32k *103.8
    (14.6s), ctx_64k *88.9 (29.7s), ctx_128k *111.6 (51.6s), ctx_256k *86.3 (122.0s). Matches
    `ornith:1.5-35b`'s own single-GPU 256k ceiling. **MULTIHOP: 3/5** — forward/reverse/distractor
    PASS (104-140 tok/s), `multihop_chain_5` and `multihop_cross_5` both FAIL(TESTS_STILL_FAIL) —
    the same aggregate 3/5 score as `ornith:1.5-35b` (whose own per-task breakdown was never
    captured, so this is a count match, not confirmed to be the identical two failing tasks) —
    consistent with sharing its lineage either way. GPU temps
    healthy (max 65°C). Full profile: 18/19 coding + 4/4 web + 3/4 L6-stepped (entities FAILS) +
    6/6 context (8k-256k) + 3/5 multihop.

#### Game-dev task group (`--task-group gamedev`, added 2026-10-08)

Purpose: test models on the code a Unity native client + existing Node.js authoritative backend
needs (the stack recommended in `~/GIT/game-engine/*.md`, cross-play with the Three.js browser
clients). The Unity Editor can't run in this harness, so the group covers only what is testable
headless: the engine-agnostic client layers (which the design docs say to keep separate from
GameObjects anyway) and the Node authority logic. Patterns come from the user's four multiplayer
games (`~/GIT/boombrawl`, `~/GIT/CarrierDominion`, `~/GIT/RetroMultiCiv`, `~/GIT/Fireline`: all raw
`ws` + JSON, server-authoritative, integer fixed-point 256 units per cell, no deltas, no wire
version negotiation). Task code is re-implemented, not copied, so `--export-task` leaks nothing.

| Task | L | Source pattern | Main traps |
|---|---|---|---|
| `cs_coord_convert` | 2 | Three.js→Unity (synthetic cm/radians) | mirrored quaternion sign, yaw wrap into [0,360), units |
| `cs_coord_bam` | 3 | CarrierDominion `client/render/coords.js` (engine z-up, 16-bit BAM) | stub is a naive three.js port: Unity yaw is `90 - bam*360/65536`, not the source's unnegated yaw; back-conversion must round like JS `Math.round` (not banker's, not away-from-zero) |
| `cs_main_thread_dispatch` | 3 | doc §5 main-thread rule | thread safety, bounded queue, re-entrant enqueue, no lock while running actions |
| `cs_protocol_codec` | 4 | boombrawl positional snap codec + RetroMultiCiv reject codes, plus a version handshake | Newtonsoft (Unity's package), int32 range, forward-compatible extra fields |
| `cs_snapshot_interp` | 4 | boombrawl/Fireline interpolators | never resurrect, teleport snap, brads shortest arc, heading vs motion (Fireline's real bug), capped extrapolation |
| `cs_predict_reconcile` | 5 | boombrawl `predict.js` + `movement.mjs` | ack `<=`, reset-then-replay order, speed before replay; must match a fixed-point server every tick over a laggy link |
| `node_room_authority` | 4 | CarrierDominion `checkAuthority` + RetroMultiCiv token buckets | identity from connection only, check order, `constructor`/`toString` as message types, per-seat bucket across reconnects |
| `node_seat_reconnect` | 4 | CarrierDominion `reconnect.js`, boombrawl reclaim | newest socket wins (4000), superseded socket's late close must not hold the seat, AI takeover/reclaim, token retirement |
| `crossplay_statehash_parity` | 5 | Fireline `canonical.js` (I32LE + FNV-1a 64) | C# `/` truncates, `int.MinValue / -1`, unit sort order, unpaired surrogates (.NET `Encoding.UTF8` substitutes U+FFFD) |

C# tasks build `src/` at **netstandard2.1 + LangVersion 9.0** (Unity's constraints: a
file-scoped namespace, `init`, or `System.Runtime.CompilerServices.Unsafe` fails to compile, as in
Unity) against a minimal UnityEngine shim; tests run at net9.0 with xunit. The canonical shim is
`task_data/_shared/UnityShim/`; each task carries a copy, guarded by `tests/test_unity_shim_sync.py`
(also guards reference solutions and regenerates the parity fixtures with `node
js/make-fixtures.js`). Every task was validated three ways: the stub fails, `*.reference.*`
passes, and single-bug mutants of the reference are each caught. Real model runs still found two
weak tests of mine (rotation axis parallel to the test vector; a prediction test that only
compared after the link settled) — trust model results over reference-only validation.

**Results, 2026-10-08 (27 models, 276 result records, ~10 h of GPU time).** Cell = **P** pass, else
weighted partial credit (0-1); `cc` = does not compile, `syn` = JS syntax error (file won't load),
`nb` = no usable file (reasoning loop / budget). Latest valid record per model × task (re-runs replace
the 6 truncated pairs). Configs: single RTX 4090 from `models/24gb.txt`/`default.txt`/`16gb.txt`
unless noted; gpt-oss:120b, qwen3.5-122b:a10b, laguna, qwen3.8-flash-next on 3×24 GB
(`3x24gb.txt`); qwen3.5:27b, qwen3-coder:30b-1m, qwen3.6:35b-A3B, deepseek-r1:32b on 2×24 GB
(`2x24gb.txt`, no single-GPU entry — cross-GPU caveat applies). gpt-oss:120b's and qwen3.8:27b's
first runs predate per-test weights, so some of their cells are unweighted.

| Model | coord (L2) | bam (L3) | disp (L3) | codec (L4) | interp (L4) | predict (L5) | room (L4) | seat (L4) | parity (L5) | pass | partial |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss:120b | 0.85 | **P** | **P** | 0.97 | 0.93 | **P** | 0.94 | 0.92 | 0.89 | 3/9 | 0.94 |
| qwen3.8-flash-next | 0.74 | **P** | 0.77 | **P** | 0.94 | **P** | **P** | **P** | 0.92 | 5/9 | 0.93 |
| equinox:31b | 0.74 | **P** | **P** | 0.90 | cc | **P** | 0.95 | **P** | 0.92 | 4/9 | 0.83 |
| qwen3.6:27b | 0.58 | **P** | **P** | 0.97 | cc | **P** | 0.95 | **P** | 0.92 | 4/9 | 0.82 |
| gemma4:31b-qat | 0.74 | **P** | 0.77 | cc | cc | **P** | **P** | **P** | 0.92 | 4/9 | 0.71 |
| qwen3.8:27b | 0.74 | **P** | 0.77 | 0.97 | cc | **P** | 0.95 | **P** | cc | 3/9 | 0.71 |
| gemma4:26b-qat | 0.74 | **P** | 0.23 | 0.94 | cc | **P** | 0.89 | 0.73 | 0.84 | 2/9 | 0.71 |
| qwen3.5-122b:a10b | 0.74 | 0.90 | **P** | cc | 0.64 | **P** | 0.84 | 0.20 | cc | 2/9 | 0.59 |
| qwen3.5:27b | 0.74 | **P** | cc | 0.62 | cc | **P** | syn | **P** | 0.92 | 3/9 | 0.59 |
| laguna-s-2.1:118b-iq4 | 0.74 | 0.90 | cc | 0.94 | cc | **P** | syn | **P** | 0.52 | 2/9 | 0.57 |
| qwen3.6:35b-A3B | 0.74 | 0.37 | 0.77 | 0.84 | cc | **P** | nb | 0.20 | 0.92 | 1/9 | 0.54 |
| qwopus3.6:35b | 0.74 | 0.37 | 0.54 | 0.84 | cc | 0.64 | syn | 0.13 | **P** | 1/9 | 0.47 |
| qwen3.5:35b | 0.48 | 0.37 | 0.54 | cc | cc | **P** | 0.63 | **P** | cc | 2/9 | 0.45 |
| qwen3-coder:30b-1m | 0.48 | 0.27 | 0.54 | cc | cc | 0.95 | 0.84 | 0.40 | 0.44 | 0/9 | 0.44 |
| quest:35b | 0.29 | 0.83 | nb | 0.75 | cc | 0.18 | 0.68 | nb | 0.92 | 0/9 | 0.41 |
| qwen3-30b:2507 | 0.48 | 0.30 | **P** | cc | cc | **P** | 0.42 | syn | cc | 2/9 | 0.36 |
| ornith:1.0-35b | 0.74 | 0.37 | cc | 0.84 | cc | **P** | syn | 0.20 | cc | 1/9 | 0.35 |
| deepseek-r1:32b | 0.74 | 0.63 | cc | 0.71 | cc | **P** | syn | 0.00 | cc | 1/9 | 0.34 |
| devstral-small-2 | 0.48 | 0.37 | cc | cc | cc | 0.90 | 0.68 | 0.20 | 0.44 | 0/9 | 0.34 |
| qwen3-coder-rtpurbo:30b | 0.48 | 0.27 | 0.54 | cc | cc | 0.49 | 0.26 | 0.20 | 0.44 | 0/9 | 0.30 |
| qwen2.5-coder:32b-q4 | 0.42 | 0.30 | cc | cc | cc | **P** | syn | 0.80 | cc | 1/9 | 0.28 |
| gpt-oss:20b | 0.74 | **P** | nb | nb | nb | nb | 0.53 | nb | nb | 1/9 | 0.25 |
| tiel-coder:35b | 0.45 | 0.47 | cc | cc | cc | **P** | syn | 0.20 | cc | 1/9 | 0.24 |
| noctrex-qwen3.6:35b | 0.74 | 0.40 | 0.77 | cc | cc | cc | nb | 0.20 | cc | 0/9 | 0.23 |
| glm4.7-flash | 0.42 | 0.27 | 0.23 | cc | 0.45 | 0.54 | syn | syn | cc | 0/9 | 0.21 |
| ornith:1.5-35b | 0.32 | 0.47 | cc | cc | cc | **P** | nb | syn | cc | 1/9 | 0.20 |
| ornith:1.5-9b | cc | 0.37 | cc | cc | cc | cc | syn | syn | cc | 0/9 | 0.04 |

Per-task: pass rate / mean partial — coord 0/27 / 0.60, bam 9/27 / 0.64, disp 5/27 / 0.42, codec
1/27 / 0.42, interp 0/27 / 0.11, predict 18/27 / 0.80, room 2/27 / 0.43, seat 8/27 / 0.46,
parity 1/27 / 0.41. Every failure was triaged; none was a task defect after the fixes in
"Findings along the way" (two weak tests, the num_ctx/min_predict defect). Determinism: equinox:31b
and qwen3.8:27b re-runs reproduced exactly; qwen3.8-flash-next's re-run was byte-identical.

**What the results say about C#/Unity ability:**
- **Tiers.** ~0.93: gpt-oss:120b and qwen3.8-flash-next (both 3×24 GB and slow here: ~10 and
  ~4.5 tok/s) — nearly every failure is a single test. ~0.82: equinox:31b (35 tok/s) and qwen3.6:27b,
  the best single-GPU C# models. ~0.71: gemma4:31b-qat, qwen3.8:27b, gemma4:26b-qat (the latter at
  ~110 tok/s: best quality per second on one GPU). Below 0.5: every A3B MoE coder/RL fine-tune
  (qwopus, quest, tiel-coder, rtpurbo, qwen3-coder, ornith) and glm4.7-flash.
- **Dense beats MoE for this work**, and coder fine-tunes are not better than their bases —
  consistent with this repo's earlier dense-vs-MoE finding on multi-step tasks.
- **Two universal gaps no model closes.** (1) The Three.js→Unity quaternion mirror: all 27 return
  `(x, y, -z, w)` (the inverse rotation) instead of `(-x, -y, z, w)` — a shared misconception, so
  model choice won't fix it; it needs a reference/test in the real project. (2) Compiling under
  Unity's rules: about half of all C# failures are compile errors (missing `using System.Linq/
  Threading/Newtonsoft.Json`, members invented on read-only types, `Mathf.Min(long, long)` picking
  the float overload, scoping errors, C# 11 `>>>` 7 times). For a Unity agent, a compile-and-test
  loop matters more than the model.
- **New failure class: in-code reasoning loops** — the Qwen3.6-A3B family and quest open the file,
  then reason in code comments until the budget runs out; gpt-oss:20b loops in prose.

**Proposed re-levelling (NOT applied — for review with the user):** pass rates contradict several
levels. coord L2→L4 (or keep as a named "handedness canary" like `python_hashmap`), disp L3→L4,
codec L4→L5, interp L4→L5, room L4→L5, predict L5→L3 (a fix-the-bugs task with an explicit rule
list is the easiest of the nine), bam/seat/parity keep L3/L4/L5. Even re-levelled, no model passes
every task at L1-L3, so all-pass Skill would read <L1 for everyone: keep `gamedev` opt-in and rank
models by mean partial credit plus pass count instead.

`cs_coord_bam` was added the same day as the rest (it was first only planned); it is a separate task
from `cs_coord_convert` so both coordinate conventions stay covered.

**Findings along the way (2026-10-08) — analysis and status:**
1. **Pass/fail hides near-misses → partial credit, IMPLEMENTED.** qwen3.8:27b's first 8 gamedev
   tasks were 2/8 by pass/fail but scored 0.85 / 0.82 / 0.97 / 0.94 on four of the failures (1-2
   tests each). Every result now carries `test_score` (`{passed, total, score, weighted}`, see
   `lib/test_results.py`), scored from the FULL runner output — dotnet's is ~100 KB and the stored
   `error_detail` keeps only 10 KB, so per-test lines must be read before truncation. Weights are
   per task (`Task.test_weights`, test-name substring → weight, default 1); for gamedev the rule is
   core-contract tests ×2-3 (e.g. exact convergence with the server, byte parity with the JS),
   argument validation ×0.5, the rest ×1, and `test_unity_shim_sync.py` fails if a weight key
   names no test. Shown as "partial credit" in the failure detail, and as a `partial` column in
   `statistics.sh --detail` (older records re-scored, unweighted, from their stored output's
   summary line). Pass/fail stays the headline and the basis of Skill; partial credit is a
   finer signal, not a replacement — a 0.97 that doesn't compile in Unity is still unusable.
2. **"Doesn't compile under Unity" is worth its own metric — PLANNED, not built.** Today a compile
   error is TESTS_STILL_FAIL with `test_score` null (= 0), the same as wrong logic. The Unity
   constraints already catch real model habits (`>>>` = C# 11, `System.Runtime.CompilerServices.
   Unsafe` absent on netstandard2.1). Proposal: when the post-edit test output has `error CS`
   lines, record `build_errors` (the CS codes), and flag `unity_incompatible` for language-version
   / missing-API codes (CS8773, CS8400, CS0518 `IsExternalInit`, CS0103/CS0234/CS0246 on
   framework names) vs. plain compile mistakes (CS0136, CS0173, CS1061...). Cheap, same parse
   point as partial credit.
3. **Port 8080 collision with llm-service-provider's gateway — FIXED both ways.** The guard refuses
   any HTTP answer (the gateway's 503 slipped through before), and with the user's go-ahead the
   harness default moved to 8099, so runs next to the gateway need no override.
4. **No real Unity validation — OUT OF SCOPE for now.** The shim plus netstandard2.1/C# 9 catches
   language and API problems but not Unity runtime behavior (IL2CPP/AOT stripping, main-thread
   rules enforced by the engine, Unity's own Newtonsoft package version). A real check needs the
   Unity Editor on Linux (~10 GB), a Personal licence activated once, and `Unity -batchmode
   -runTests` with the Unity Test Framework against a project template that copies these sources
   in. Worth it only if gamedev results start driving real Unity decisions.
5. **gpt-oss:120b decodes at ~9-12 tok/s on gamedev tasks** (3×24 GB, all on GPU) vs ~70 on
   short-prompt coding tasks. The harness's tok/s is decode-only (llama-server's
   `predicted_per_second`), so this is not prompt processing. It matches this model's historical
   ~10 tok/s on `csv_nordic_property` (also a ~6k-token prompt), so it is a reproducible long-prompt
   decode slowdown on this rig, not a fault in this run; the cause (3-way split at deeper KV,
   q8_0 KV, reasoning length) is NOT established. Wall times per gamedev task: 3-12 min.
6. **Weak tests found by real model runs, not by reference/mutant validation** — fixed (rotation
   axis parallel to the test vector; prediction compared only after settling). Lesson recorded:
   a model's wrong-but-plausible answer is a better test of the test than a hand-made mutant.
7. **Stale results** from pre-fix task versions moved to `output/stale/` so `statistics.sh`
   (which reads every `output/*.json`) doesn't mix them in. Do the same after any future task fix
   that changes outcomes.
8. **Context/budget defect, FIXED 2026-10-08 (sweep 4):** the two Node tasks had no `num_ctx` and ran
   at the 8192 default, so thinking models (qwen3.6:35b-A3B, noctrex-qwen3.6:35b, quest:35b) were cut
   off mid-file (NO_BLOCKS, finish=length); three C# tasks had `min_predict=8000` and truncated quest
   and gpt-oss:20b mid-reasoning. All 9 tasks now use `num_ctx=24576` + `min_predict=12000`, guarded by
   `test_context_fits_prompt_plus_thinking_budget`; the 6 affected (model, task) pairs were re-run.
   **All 6 still failed at the full 12000 tokens**, and for a genuine reason: the Qwen3.6-A3B family
   and quest:35b open BEGIN_FILE, then reason INSIDE the code as comments ("// Actually, let me
   restart the implementation...") until the budget runs out; gpt-oss:20b loops "Ok. Let's
   implement." The fix removed the harness limit; what remains is model behavior (in-code reasoning
   loops), which more budget would not cure.
9. **qwen3.8-flash-next is ~2× slower than documented on this rig now — OPEN.** Gamedev decode ~4.5 tok/s;
   the control `python_hashmap` run gave 10.6 tok/s against the documented 23.0 on the same pinned
   `67a17c17c` and the same `3x24gb.txt` config (no concurrent I/O, 77 GB RAM free — I first wrongly
   blamed a concurrent download). So there are two effects: a rig-level ~2× slowdown since the
   2026-09-03 measurement, and a further ~2× at gamedev's `num_ctx=24576` (with `--fit`, a bigger KV
   cache leaves fewer experts in VRAM). Leading hypothesis for the first, untested: the binary was
   rebuilt with `GGML_CUDA_GRAPHS=ON` (added to build-llama.sh 2026-09-04), while the 23 tok/s
   number predates that flag. Test: rebuild 67a17c17c with `-DGGML_CUDA_GRAPHS=OFF` (~25 min), re-run
   the control. Capability results are unaffected (byte-identical re-run).

#### What NOT to do

- Don't implement multi-turn autonomous "agent loops" in v1.
- Don't auto-install dependencies or mutate the user's environment.
- Don't rely on network services beyond Ollama and package restores already required by tasks.
- Don't use `shell=True` in subprocess calls.
- Don't add a `prompting.py` — prompt building lives in `tasks.py`.
