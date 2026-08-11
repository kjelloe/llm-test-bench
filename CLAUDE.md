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
  devstral-small-2 (24B dense) similarly spills at ~5.2 tok/s (819s) at ctx=131072 on 24GB
  — wall_time_budget_s=300 flags it as PASS_BUT_SLOW. Speed on llama-server: ~45 tok/s
  (2.6× faster than ollama's ~17 tok/s for the same model at normal context sizes).
  qwen2.5-coder:32b Q4_K_M (~18.5 GB weights): CONFIRMED 2026-06-26 full 33-task on 2×24 GB:
  28/33 at 36.5 tok/s, Skill L2. CODING PERFECT (19/19) — the strongest coder tested; passes
  csv_nordic_property, node_csv_parser, and python_expr_eval (deepseek-r1:32b loops on expr_eval
  indefinitely; this model solves it cleanly). Passes node_para_turret (L4), node_para_entities (L5),
  node_para_combat (L6), multihop+distractor (3/3). FAILS: node_para_core (L3 game logic gap —
  same failure as qwen3-next:80b, quest:35b, Q5_K_M variant), node_paratrooper (L6 universal wall).
  CONTEXT CEILING: server silently caps at ctx=32768 on 2×24 GB despite max_ctx=131072 config.
  KV math predicts 65536 should fit (4 GB/GPU at q8_0 + 9.25 GB/GPU weights = 13.25 GB < 24 GB),
  but server internally caps at 32768 (same behavior as single-GPU). Root cause unknown — likely
  CUDA overhead or flash_attn workspace allocation. max_ctx=32768 set in 2x24gb.txt to match reality.
  context_64k/128k → CTX_TRUNCATED; context_256k → SKIPPED_CTX (max_ctx=131072 arch limit).
  Passes python_hashmap with q8_0 KV — the _EMPTY precision issue is specific to 27B dense models, not 32B.
  Added to models/24gb.txt (single-GPU coding tasks only) and models/2x24gb.txt (full run).
  deepseek-r1:32b Q4_K_M (~20 GB): with max_ctx=32768 scores 23/29 (26 eligible) at ~29 tok/s
  (2026-05-22). 18/19 coding at 31.4 tok/s (2026-05-24 coding run, corrected flags) —
  python_expr_eval is a structural capability gap: model enters an infinite reasoning spiral
  ("code is correct. But...") and exhausts any token budget without emitting code; not fixable
  by increasing num_predict or num_ctx. Multihop/distractor
  all PASS at ~21 tok/s. ctx≥64k SKIPPED (max_ctx=32768 hard cap). Use max_ctx=32768 in model
  config to unlock context_32k and multihop tasks on 24 GB.
  qwq:32b Q5_K_M (~22 GB): effectively unusable on 24 GB — KV thrashing reduces throughput
  to ~6 tok/s; 11/24 tasks pass. Server silently caps max_ctx=65536 → 32768 when VRAM is
  exhausted. Needs true 32 GB to be useful. Use `max_ctx=32768` in model config to avoid
  CTX_TRUNCATED errors on 24 GB.
  codestral:22b (dense 22B, ~14 GB): ~50 tok/s, 15/24. Hard architecture limit of 32k
  tokens (Codestral v0.1) — CTX_TRUNCATED on context_64k, context_128k, multihop, and
  distractor tasks. No workaround; limit is baked into the weights.
  **mellum2:12b-thinking** (JetBrains, MXFP4 MoE A2.5B active, ~6.5 GB, single RTX 4090):
  CONFIRMED 2026-06-26 full 33-task: 20/33 at 254.1 tok/s; Skill L1. Fastest model benchmarked.
  Context ceiling max_ctx=32768 — SKIPPED_CTX at 64k+ on real 8 GB hardware.
  Coding (13/19): passes node_csv_parser (L3), python_expr_eval (L4), python_tokenizer (L4).
  Fails: csv_nordic_property (L3), node_slugify (L2 — caps Skill at L1), python_multifile_rename (L2),
  node_debounce (L3), python_dijkstra (L5), python_hashmap (L5 NO_BLOCKS TRUNCATED).
  Para: passes node_para_core (L3) + node_para_turret (L4 TRUNCATED); fails node_para_entities (L5),
  node_para_combat (L6). SURPRISE: node_para_core PASSES where qwen2.5-coder:32b-q4 FAILS.
  node_csv_parser PASSES where qwen3-next:80b and quest:35b fail.
  python_hashmap is a hard ceiling for thinking models — 12000-token budget entirely consumed
  by reasoning; 12000 tokens of <think> with no BEGIN_FILE emitted. Not fixable by increasing budget.
  Multihop: passes forward + distractor; fails reverse. Requires Ampere+ (MXFP4).
  phi4-reasoning-plus:14b (thinking, ~9 GB): ~58 tok/s but INCOMPATIBLE with this benchmark.
  Loops in a reasoning planning phase ("I'll produce the file content with the modifications"
  repeated indefinitely) and never emits BEGIN_FILE regardless of num_predict — confirmed at
  both 4800 and 12000 tokens (0/13 on targeted re-run at 12k). Format compliance issue: the
  model was trained to emit answers inline, not in structured file blocks. Do not benchmark.
  llama4-scout:17b (MoE 17B active / 109B total, ~60 GB hybrid): ~3.3 tok/s — fully
  CPU-bound on 24 GB VRAM; 109 GB weights live in RAM. Quality is high (19/24) but throughput
  is impractical. csv_nordic_property times out (model_timeout=600s at 3.3 tok/s ≈ 2000 max
  tokens). context_128k passes SLOW (1216s). Needs 64 GB+ VRAM to be GPU-resident and fast.
  CONFIRMED 2026-08-11 (3×24 GB spot check): 7/10, 10-29 tok/s — REJECTED for 3x24gb.txt.
  Speed: 28-29 tok/s at ctx=8192, 10-21 tok/s at ctx=32768 (KV pressure even GPU-resident).
  FAIL: csv_nordic_property (TESTS_STILL_FAIL at 237s — prior TOOL_ERROR was timeout; now
    confirmed structural capability gap, not solvable by speed), python_hashmap (L5, 17 tok/s),
    node_paratrooper (L6 universal wall). PASS: node_csv_parser (L3), python_expr_eval (L4),
    node_para_core (L3). Prior "19/24" result was inflated by SKIPs — actual capability ≈ 7/10.
  Not worth adding to 3x24gb.txt: same VRAM footprint (~60 GB) as gpt-oss:120b, far lower quality.
  **glm4.7-flash** (Zhipu AI / noctrex, MXFP4 MOE, ~16 GB, single RTX 4090): 17/19 coding
  at 112 tok/s (2026-06-22). CONFIRMED 2026-06-26 full 33-task run: 29/33 at 110.9 tok/s avg.
  Effective Skill L4. Fails python_hashmap (L5), python_dijkstra (L5), node_paratrooper (L6
  from-scratch), context_256k (capability gap — wrong answer after 476s at 45 tok/s, not OOM).
  SURPRISE: passes node_para_entities (L5) and node_para_combat (L6) — full stepped chain through L6.
  Context: passes 8k–128k cleanly (128k at 63.3 tok/s); 256k capability failure.
  NOTE: ~16 GB model requires 24 GB VRAM to run with useful context — minimal KV headroom on 16 GB GPU.
  Without CUDA_VISIBLE_DEVICES restriction, llama-server distributes layers to both GPUs even without
  tensor_split; use `./gpu-mode.sh single` for clean single-GPU benchmarks. Added to models/24gb.txt.
  REGRESSION NOTE (2026-07-23, llama-server 10094, CONFIRMED 2026-07-23 re-run): python_config_loader FAIL
  (L2 TESTS_STILL_FAIL — previously PASS in 2026-06-26 33-task run). Caps Skill at L1 on this binary.
  csv_nordic_property PASS (still passes). Also context_256k TOOL_ERROR (7200s, no max_ctx cap — fixed:
  max_ctx=131072 now set in default.txt). Root cause: kq-mask f16 change (#25370) in llama-server 10094.
  **qwen3-30b:2507** (unsloth, Q4_K_M A3B MoE, ~17 GB, single RTX 4090): CONFIRMED 2026-07-03
  full 37-task run: 32/37 at ~163 tok/s avg. July 2026 re-instruction fine-tune of Qwen3-30B-A3B-Instruct.
  Skill L2 (full run: python_fastapi_endpoint L3 TESTS_STILL_FAIL caps it; Skill L4 in coding-only context).
  Coding: 18/19 (python_hashmap L5 capability gap). Web: 3/4 (python_fastapi_endpoint FAIL).
  L6 stepped: passes core/turret/combat; FAILS node_para_entities (L5, step 3 gap). node_paratrooper FAIL (universal L6 wall).
  Context (single 24 GB): PASS 8k/16k/32k/64k; FAIL 128k (TOOL_ERROR 3600s, 0 tok/s — KV exhaustion at 131072 ctx);
  256k SKIPPED_CTX (arch limit 131072). Multihop: 3/3 PASS at 65536 ctx (16-17 tok/s).
  Context (2×24 GB): context_128k CONFIRMED PASS at 63.4 tok/s (2026-07-22) — tensor_split resolves KV exhaustion.
  context_256k SKIPPED_CTX (architecture hard limit n_ctx_train=131072, not a VRAM constraint).
  Speed: ~160-175 tok/s at coding ctx; 9.2 tok/s at 64k (KV spill single GPU); 16-17 tok/s at multihop 65k ctx.
  Context ceiling: max_ctx=65536 set in 24gb.txt — 128k/256k become SKIPPED_CTX. max_ctx=131072 in 2x24gb.txt.
  Added to models/24gb.txt and models/2x24gb.txt.
  **qwen3-30b:deepseek** (noctrex, Qwen3-30B-A3B DeepSeek-Distill-2507 MXFP4 MoE, ~15.9 GB, Ampere+):
  CONFIRMED 2026-08-05 spot check: 7/10 at 185.9 tok/s — REJECTED (below 8/10 threshold).
  PASS: python_safe_div (L1), node_slugify (L2), python_lru_cache (L2), node_csv_parser (L3),
    python_tokenizer (L4), python_expr_eval (L4), node_para_core (L3).
  FAIL: csv_nordic_property (L3, TESTS_STILL_FAIL — qwen3-30b:2507 PASSES this; distillation regressed it),
    python_hashmap (L5, same base gap), node_paratrooper (L6, universal wall).
  No reasoning spiral on python_expr_eval (PASS, 8.4s clean — distillation did NOT introduce DeepSeek spiral).
  Speed 186 tok/s (+14% vs 163 tok/s for 2507 base) irrelevant given quality regression. Do not use.
  **qwen3-coder:30b-mxfp4** (Face314, MXFP4 A3B MoE, ~15.9 GB, Ampere+ required): CONFIRMED 2026-06-27
  18/19 coding at 172 tok/s; node_paratrooper TESTS_STILL_FAIL (same universal L6 wall, 3.6k tokens).
  Same Qwen3-Coder-30B-A3B architecture as qwen3-coder:30b-1m. Same coding failure as qwen3-30b:2507
  (python_hashmap capability gap). MXFP4 is ~7% slower than Q4_K_M (172 vs 185 tok/s) — only
  advantage is 1 GB smaller VRAM footprint. Skill L4 coding. Added to models/24gb.txt.
  **MXFP4 vs Q4_K_M for A3B MoE on RTX 4090 (2026-06-27)**: for the Qwen3-30B-A3B architecture,
  Q4_K_M is ~7% faster than MXFP4 (185 vs 172 tok/s). MXFP4 saves ~1 GB VRAM but produces no
  quality difference. Prior noctrex experiments showed MXFP4 at no speed advantage over Q4_K_M for
  Qwen3.5-35B (noctrex MXFP4 was 25% slower than bartowski Q4_K_M). Conclusion: for A3B MoE models,
  Q4_K_M is the preferred format on RTX 4090 — smaller file size and faster inference.
  **lfm2:8b** (Liquid AI, MXFP4 A1B MoE, ~4.5 GB, single RTX 4090): CONFIRMED 2026-06-27
  3/10 at 320.8 tok/s — new speed record (fastest model ever benchmarked; beats mellum2:12b at
  254 tok/s). Terrible quality: fails node_slugify (L2), csv_nordic_property, node_csv_parser (L3),
  python_expr_eval (L4), python_hashmap (L5), node_paratrooper. node_para_core NO_BLOCKS (format
  failure at L3 complexity). Not useful beyond L1 tasks. Do not add to any model set.
  **ernie4.5:21b** (Baidu / noctrex, MXFP4 A3B MoE, ~11.5 GB): CONFIRMED 2026-06-27 5/10 at
  190 tok/s. First Baidu model benchmarked. Fails node_slugify (L2), csv_nordic_property +
  node_csv_parser (L3), python_hashmap. Cold-start 51s. Not competitive; rejected.
  **Huihui-MoE-24B-A8B** (mradermacher, i1-Q4_K_M MoE, ~13.9 GB, single RTX 4090, no Ampere+ required):
  CONFIRMED 2026-07-28 spot check: 4/10 at 132.6 tok/s. REJECTED.
  PASS: python_safe_div (L1), python_lru_cache (L2), python_tokenizer (L4), python_expr_eval (L4).
  FAIL: node_slugify (L2, NO_BLOCKS — 73s in <think> block, never emits BEGIN_FILE; format pathology),
    csv_nordic_property (L3, TESTS_STILL_FAIL — 120s wrong solution; capability gap),
    node_csv_parser (L3, NO_BLOCKS TRUNCATED — 219s, 16k budget exhausted in think block),
    python_hashmap (L5, TESTS_STILL_FAIL — 30s, capability gap not format issue),
    node_para_core (L3), node_paratrooper (L6).
  24B total / 8B active. A8B active-param tier does NOT outperform A3B (qwen3-30b:2507 scores 8/10 at
  181 tok/s with A3B active). Architecture/training dominates over active parameter count. The <think>
  block format pathology (never emits BEGIN_FILE on complex tasks) is the same root cause as huihui-60b's
  [thinking: BEGIN_FILE...] wrapper — different encoding, same non-compliant format family. Do not retry.
  **GroveMoE-Inst** (inclusionAI / noctrex, MXFP4 MoE, ~17.1 GB, single RTX 4090, Ampere+ required):
  CONFIRMED 2026-07-28 spot check: 0/10 at 124.7 tok/s — REJECTED (inference corruption, NOT a capability failure).
  ALL 10 tasks NO_BLOCKS: model outputs `!!!...!!!` (exclamation-mark garbage) on every prompt — 154k tokens
  generated in 26:09 with zero useful output. Architecture: inclusionAI GroveMoE, up-cycled from
  Qwen3-30B-A3B-Base with "adjugate experts" (shared expert computation reuse); 33B total / ~3.14-3.28B active
  (A3B tier). Root cause: `grovemoe` architecture type not correctly supported by llama-server 10094.
  Do not retry on this binary — would need a llama-server build that adds `grovemoe` arch support.
  **Moonlight-16B-A3B** (Kimi / noctrex, MXFP4 A3B MoE, ~8.7 GB, single RTX 4090, Ampere+ required):
  CONFIRMED 2026-07-26 spot check: 4/10 at 175.7 tok/s. REJECTED.
  PASS: python_safe_div (L1), python_lru_cache (L2), python_tokenizer (L4), node_para_core (L3 — same
    surprise pass as mellum2:12b; Kimi architecture handles game-state logic at L3).
  FAIL: node_slugify (L2) caps Skill at L1; csv_nordic_property + node_csv_parser (L3);
    python_expr_eval (L4), python_hashmap (L5), node_paratrooper (L6).
  Speed is impressive for 8.7 GB (125–197 tok/s, avg 175.7) but capability is below threshold.
  Same A3B active-param ceiling as ernie4.5:21b and lfm2:8b. New architecture family (Kimi MoE)
  but does not outperform established A3B models on coding tasks. Do not benchmark further.
  **granite4:small** (IBM Granite 4.0 H-Small / noctrex, MXFP4 MoE, ~18.5 GB): CONFIRMED 2026-06-27
  7/10 at 77.6 tok/s — much slower than expected for MXFP4 (~110 est). Passes node_csv_parser +
  node_para_core; fails csv_nordic_property, python_hashmap, node_paratrooper. Below threshold.
  **qwen3-coder-reap:25b** (noctrex, MXFP4 A3B MoE, ~13.1 GB): CONFIRMED 2026-06-27 7/10 at
  155 tok/s. REAP post-training; fails csv_nordic_property (L3), python_hashmap, node_paratrooper.
  Inferior to qwen3-30b:2507 on both quality and speed. Rejected.
  **qwen3-next:80b Q4_K_M** (bartowski, ~45 GB): CONFIRMED 2026-06-27 DOES NOT FIT on 2×24 GB.
  cudaMalloc fails allocating 23.9 GB on device 0 with tensor_split=1|1 — model share exceeds
  24 GB even before KV cache. Minimum tier: 3×24 GB (72 GB). The noctrex MXFP4 (~41 GB) fits
  on 48 GB; this Q4_K_M does not. Use in models/3x24gb.txt with tensor_split=1|1|1.
  **Qwen3-VL-235B-A22B Q3_K_M** (unsloth, 112 GB, capability preview 2026-06-28):
  Run on current hardware (86 GB DDR5 + 48 GB VRAM) at ngl=30→37, tensor_split=1|1, 2.7–2.8 tok/s.
  VRAM split: ~20 GB on RTX 4090 + ~17 GB on RTX 3090 = 37 GB GPU-resident; ~75 GB in DDR5.
  PASS: python_hashmap (L5) — definitive at Q3; correctly implements tombstone algorithm.
    All benchmarked models below 80B (glm4.7-flash, qwen3-next:80b, both qwen3-30b variants,
    deepseek-r1:32b, etc.) fail this task. 235B passes cleanly.
  PASS: node_para_core (L3) — passes where qwen3-next:80b, quest:35b, qwen2.5-coder:32b-q4 all fail.
  FAIL: node_paratrooper (L6) — TESTS_STILL_FAIL at ngl=37, 1588s, 3.8k tokens; constructor correct
    (initial state tests pass), game loop logic wrong. Same universal L6 wall as all other models.
    NOT a timeout — generation completed at 2.8 tok/s; the model simply cannot solve this task.
  Speed: 2.8 tok/s at Q3 with ngl=37. 72s startup.
  Capability verdict: clearly higher tier than all benchmarked <80B models on python_hashmap and
    node_para_core discriminators, but hits the same node_paratrooper wall as every other model tested.
  **qwopus3.6:35b** (jashepp, Qwen3.6-35B-A3B coder fine-tune, MXFP4 MOE Q8_0-Imatrix, ~19.8 GB, single RTX 4090, Ampere+ required):
  CONFIRMED 2026-07-22 full 37-task run: Skill L4 (effective). 160.0 tok/s avg — fastest model with perfect coding score.
  Coding PERFECT: 19/19 at 161.8 tok/s. Web: 3/4 (python_fastapi_endpoint FAIL — coder fine-tune breaks whitespace validation).
  Base model: Qwen3.6-35B-A3B (same as noctrex-qwen3.6:35b which scores 32/33); jashepp's Q8_0-Imatrix recipe runs +34% faster.
  Para (single 24 GB): node_para_core PASS (L3), node_para_turret PASS (L4). node_para_entities: GPU froze during prefill
    (0 tok/s, 3600s wall) — max_ctx=32768 leaves ~0.7 GB VRAM free; step-3 prompt ~7k tokens exhausts compute headroom.
  Para (2×24 GB): CONFIRMED 2026-07-26 4/4 PASS at 122.7 tok/s avg — tensor_split resolves VRAM headroom completely.
    node_para_entities *133.9 tok/s, node_para_combat *130.6 tok/s. node_paratrooper TESTS_STILL_FAIL (L6 universal wall).
  Context (single 24 GB, max_ctx=32768): context_64k/128k/256k → SKIPPED_CTX. 8k PASS (134 tok/s), 16k PASS (130 tok/s),
    32k PASS (106 tok/s), multihop_forward PASS (102 tok/s), multihop_reverse PASS (103 tok/s), distractor_notes PASS (101 tok/s).
    VRAM hang is specific to long prefill prompts; does NOT affect context tasks at ctx=32768.
  Context (2×24 GB, max_ctx=131072): CONFIRMED 2026-07-26 5/6 PASS. ctx_64k *114.7 tok/s PASS (113s);
    ctx_128k PASS (214s wall — 128k prefill dominates); ctx_256k SKIPPED_CTX (arch limit 131072).
    ctx_8k/16k/32k PASS but reported tok/s anomalous (0.7/0.4/0.3 — prefill-dominated wall-time avg for ~20 output tokens;
    actual generation speed confirmed 88–138 tok/s from L6 run).
  Added to models/24gb.txt + 2x24gb.txt. f16 KV. 4090 power spikes to 350W TDP. max_ctx=32768 (single GPU), max_ctx=131072 (2×24 GB).
  agents-a1:35b (same jashepp family, different base model): FAIL csv_nordic_property (L3), 7/10, 159.8 tok/s, Skill L2 — rejected.
  Comparison: qwopus3.6 base (Qwen3.6-35B-A3B) accounts for the quality gap vs agents-a1 (unknown base).
  **equinox:31b** (jashepp, dense 31B MXFP4 Q8_0-Imatrix, ~16.4 GB, single RTX 4090, Ampere+ required):
  CONFIRMED 2026-07-04 37-task full run: 32/37 at 35.5 tok/s avg. Skill L4.
  Coding PERFECT: 19/19 (all L1–L4 + python_dijkstra + python_hashmap (L5) + node_para_combat (L6)).
  Web PERFECT: 4/4 (including python_fastapi_endpoint — field_validator + .strip()).
  Only single-24 GB model CONFIRMED with 19/19 coding + 4/4 web simultaneously. Dense ≥31B is the cutoff for fastapi_endpoint.
  FAIL: node_para_entities (L5 step 3 gap — passes steps 1-2 and 4 but not step 3), node_paratrooper (L6 universal wall).
  Context ceiling: 32k on single 24 GB. f16 KV on dense 31B: ~5.5 GB at 32k (fits), ~11 GB at 64k + 16.4 GB weights ≈ 27.4 GB > 24 GB.
  max_ctx=32768 in 24gb.txt: context_64k/128k/256k and multihop/distractor → SKIPPED_CTX. For 64k+ context use 2×24 GB.
  2×24 GB (CONFIRMED 2026-07-22, 6/6 PASS): context_64k *31.1 tok/s, context_128k *27.3 tok/s, multihop/distractor *34.3 tok/s.
  python_hashmap PASS at 37.8 tok/s on 2×24 GB — no regression at tensor_split=1|1 (f16 KV maintained). max_ctx=131072 in 2x24gb.txt.
  Speed: ~40-43 tok/s at ctx=8192, ~32-36 tok/s at ctx=32768. 4090 power spikes to 350W TDP (normal for dense 31B fully GPU-resident). f16 KV (unknown architecture, safe default).
  **gemma4:31b-qat** (lmstudio-community, dense 31B QAT Q4_0, ~16.4 GB, single RTX 4090, no Ampere+ required):
  CONFIRMED 2026-07-24/25 complete: 31/37, Skill L4. QAT = quantization-aware training on Q4_0, strictly
  better than PTQ Q4_K_M at same bit rate. No Ampere+ requirement (Q4_0, not MXFP4).
  Coding: 18/19 at 42.3 tok/s. FAIL node_csv_parser (L3 — generates 'export function parseCSV' which
    conflicts with existing declaration in stub; ESM syntax conflict; consistent gap, not fluke).
  PASS csv_nordic_property (L3) — dense architecture fixes the Gemma4 A4B MoE structural gap.
  PASS python_dijkstra + python_hashmap (both L5) — QAT int4 preserves L5 precision at f16 KV.
  Web: 4/4 PERFECT at 42.2 tok/s — including python_fastapi_endpoint (field_validator + .strip()).
    Dense ≥31B cutoff for python_fastapi_endpoint confirmed for Gemma 4 architecture.
  L6 stepped: 3/4 — core (L3) PASS, turret (L4) PASS, entities (L5) FAIL (NO_BLOCKS at ctx=8192;
    step 3 prompt truncates mid-output — same failure mechanism as equinox:31b), combat (L6) PASS.
  Multihop+distractor: 3/3 PASS at 36.8 tok/s (ctx=32768).
  Context (single 24 GB): 8k PASS (37.8 tok/s), 16k PASS (38.2 tok/s), 32k PASS (0.7 tok/s —
    bandwidth-saturated on single GPU); 64k/128k/256k SKIPPED_CTX. max_ctx=32768.
  Context (2×24 GB): CONFIRMED 2026-07-25 (5/6 PASS): ctx_8k *34.5, ctx_16k *34.6, ctx_32k *32.4
    (vs 0.7 tok/s single GPU), ctx_64k *30.9, ctx_128k *27.9 tok/s SLOW (492s — same tier as
    equinox:31b 27.3 tok/s). context_256k SKIPPED_CTX (architecture limit max_ctx=131072). max_ctx=131072.
  Speed: ~40-43 tok/s at coding ctx — same tier as equinox:31b (~40 tok/s). f16 KV (unknown arch).
  Identical capability profile to equinox:31b except node_csv_parser. Added to 24gb.txt + 2x24gb.txt.
  **qwen3-48b:a4b** (DavidAU, Qwen3-48B-A4B 12-expert distill, Q4_K_M, ~19 GB, single RTX 4090):
  CONFIRMED REJECTED 2026-07-25: 4/10, node_slugify (L2) FAIL caps Skill at L1.
  csv_nordic_property TOOL_ERROR (600s, 0 tok/s) — server froze during prefill at ctx=32768 (VRAM exhaustion;
  same GPU kernel stall as qwopus3.6:35b on node_para_entities). Speed collapse: 145 tok/s at ctx=8192
  → 35 tok/s at ctx=32768 → 13.2 tok/s for long generation (severe KV thrash). DavidAU 12-expert distill
  merge degrades quality. Do not retry.
  **huihui-60b** (noctrex, Huihui-MoE-60B-A3B MXFP4 MOE, 2-part ~30.3 GB, 2×24 GB, Ampere+ required):
  CONFIRMED REJECTED 2026-07-25: 4/10, 154.4 tok/s on 2×24 GB.
  node_slugify NO_BLOCKS — model wraps entire output in '[thinking: BEGIN_FILE ...]' format; parser never
  finds standalone BEGIN_FILE. Even if format were fixed, remaining A3B capability ceiling failures
  (csv_nordic_property, node_csv_parser, python_tokenizer, python_hashmap, node_paratrooper) cap at 5/10.
  155-168 tok/s on 2×24 GB but quality does not justify; A3B architecture failures identical to
  qwen3-30b:2507/ornith:35b pattern. Do not retry.
  **laguna-s-2.1:118b** (Poolside, 118B MoE A8B, wimmmm IQ3_XXS, ~42.1 GB, 2×24 GB):
  CONFIRMED 2026-07-27 full 19-task coding: 17/19 at 96.1 tok/s avg. Skill L3 (coding, IQ3_XXS).
  Poolside-AI's coding + agentic model; ~8B active params per token — largest A8B tier benchmarked.
  IQ4_XS (58.4 GB) OOM on 2×24 GB (29.2 GB/GPU → cudaMalloc fail on RTX 4090). IQ3_XXS (42.1 GB)
  fits fully GPU-resident on 48 GB. IQ4_XS on 3×24 GB is the definitive test; file at allmodels/.
  PASS (17): all L1–L2 (node_slugify, python_safe_div, dotnet_sas, python_multifile_rename), all L3
    except CSV pair (python_lfu_cache, python_minheap, node_memoize_bug, python_ledger_bug, node_debounce,
    awk_csv_stats, java_word_freq), python_lru_cache, python_expr_eval (L4), python_tokenizer (L4),
    python_merge_intervals (L4), python_dijkstra (L5), python_hashmap (L5!).
  FAIL: csv_nordic_property (L3, TESTS_STILL_FAIL — 68s full generation, wrong solution; capability gap,
    NOT IQ3_XXS precision loss), node_csv_parser (L3, TESTS_STILL_FAIL — 9.5s quick fail; quoted-comma edge case).
  Speed: 96–105 tok/s; python_dijkstra anomaly at 38.3 tok/s (KV pressure during long generation).
  python_hashmap PASS at IQ3_XXS is a strong quality signal — L5 precision preserved at 3-bit quantization.
  csv_nordic_property failure is structural (68s full generation = model tried and produced wrong logic), not
    quant precision — IQ4_XS is unlikely to flip it. node_csv_parser also structural (same 9.5s quick-fail
    as qwen3-next:80b and many A3B models on this task). IQ4_XS remains worth testing for completeness.
  REQUIRES: ./gpu-mode.sh multi and --model-timeout 1200.
  **qwen3-coder-rtpurbo:30b** (mradermacher, Qwen3-Coder-30B-A3B RTPurbo fine-tune, i1-Q4_K_M, ~17.3 GB [MoE], single RTX 4090, no Ampere+ required):
  CONFIRMED 2026-08-05: 18/19 coding at 211.4 tok/s, 2/4 web. Added to 24gb.txt.
  Coding PASS (18): all L1–L4 + python_dijkstra (L5). csv_nordic_property + node_csv_parser (both L3) PASS
    — base qwen3-coder:30b-1m fails both; RTPurbo post-training fixed them.
  Coding FAIL (1): python_hashmap (L5, base Qwen3-Coder capability gap shared by all qwen3-coder variants).
  Web PASS: bash_preflight (L2), node_express_validation (L3).
  Web FAIL: python_config_loader (L2, partial-method-completion, same gap as qwen3-coder:30b-1m),
    python_fastapi_endpoint (L3, A3B coder fine-tune pattern — Field(min_length=1), not field_validator+.strip()).
  Speed: 211.4 tok/s coding avg — new single-GPU speed record at 18/19 quality tier;
    31% faster than qwopus3.6:35b (161.8 tok/s, 19/19). Token efficiency 2.308 p/k.
  GLM-4.7-Flash-REAP (same scout run): 6/10 REJECTED — REAP degraded csv_nordic_property + node_csv_parser
    (both were PASS in base glm4.7-flash); post-training can regress L3 CSV capability.
  **gpt-oss:120b** (OpenAI, MXFP4 MoE single-file ~60 GB, ggml-org, 3×24 GB required):
  CONFIRMED 2026-08-11 full 37-task (3×24 GB, tensor_split=1|1|1): **32/34 eligible, Skill L6**.
  **PERFECT 19/19 coding + PERFECT 4/4 web** — first model to achieve both simultaneously.
  **First model to complete the full L6 stepped chain**: node_para_core (L3) + node_para_turret (L4)
    + node_para_entities (L5) + node_para_combat (L6) ALL PASS. node_paratrooper (L6 from-scratch) FAIL
    (universal wall — no model of any size has passed this task).
  Context: context_8k PASS (62 tok/s), context_16k TOOL_ERROR (1200s transient restart; context_32k
    immediately after PASS — not a capability issue), context_32k PASS (58 tok/s).
    context_64k/128k/256k SKIPPED_CTX (max_ctx=32768 — fixed to 65536 post-run; context_64k rerun pending).
  Multihop: forward/reverse/distractor all PASS (~55 tok/s).
  Speed: ~55 tok/s coding avg, 8.8-26 tok/s on para tasks (long generation), 58-73 tok/s context.
    node_para_combat: 829s at 8.8 tok/s — very long output on L6 game-state task.
    python_tokenizer: 53s at 24 tok/s. Slower than estimated 90 tok/s — model generates lengthy outputs.
  thinking=true confirmed working — no planning loops at 3×24 GB.
  Temps: GPU0 34/42/54°C (min/avg/max), GPU1 38/49/66°C, GPU2 41/56/66°C — all healthy.
  On single 24 GB: required n_cpu_moe=35 CPU offload → ~17 tok/s RAM-bound. On 3×24 GB: fully GPU-resident.
  max_ctx=65536 now set in 3x24gb.txt (was 32768; q8_0 KV at ~4 GB/GPU should fit ctx=65536 on 12 GB total).
  **web task group results (2026-07-02/03 + 2026-07-24 + 2026-08-05, --task-group web, llama-server, 4 tasks)**:
  - noctrex-qwen3.6:35b: 4/4 at 116.7 tok/s — PASS python_fastapi_endpoint (field_validator with .strip())
  - equinox:31b: 4/4 at 40.3 tok/s — PASS python_fastapi_endpoint (field_validator with .strip())
  - qwen2.5-coder:32b-q4: 4/4 at 33.3 tok/s — PASS python_fastapi_endpoint (field_validator with .strip())
  - gemma4:31b-qat: 4/4 at 42.2 tok/s — PASS python_fastapi_endpoint. Dense 31B QAT (Gemma 4 arch).
    Confirms dense ≥31B cutoff is architectural, not specific to Qwen base models.
  - qwen3-coder:30b-1m: 2/4 at 150.8 tok/s — FAIL python_config_loader (L2) + FAIL python_fastapi_endpoint (L3); partial-method-completion likely drops module-level env-var logic
  - quest:35b: 2/4 at 131.2 tok/s — FAIL python_config_loader (L2) + FAIL python_fastapi_endpoint (L3); "35B" is total params, A3B active = same MoE tier as failing cluster; RL training does not compensate
  - glm4.7-flash: 3/4 at 112.8 tok/s — FAIL python_fastapi_endpoint (uses Field(min_length=1), passes "   " as valid name instead of rejecting it)
  - qwen3-30b:2507: 3/4 at 162.1 tok/s — same FAIL as glm4.7-flash (same Field(min_length=1) approach)
  - qwopus3.6:35b: 3/4 at 161.8 tok/s — FAIL python_fastapi_endpoint; same cluster as glm4.7-flash + qwen3-30b:2507 despite sharing Qwen3.6-35B-A3B base with noctrex (which passes). Confirms failure is fine-tune dependent, not architecture.
  - qwen3-coder-rtpurbo:30b: 2/4 at 192.9 tok/s — FAIL python_config_loader (L2) + FAIL python_fastapi_endpoint (L3). Same 2-task failure pattern as qwen3-coder:30b-1m. Confirms RTPurbo shares the base coder model's structural Python gap.
  - python_fastapi_endpoint: cutoff is dense ≥31B or specifically noctrex-qwen3.6:35b (full instruction
    fine-tune); all A3B coder/RL/agent fine-tunes fail regardless of base model or param count.
    gemma4:31b-qat PASS (2026-07-24) confirms the ≥31B dense cutoff holds across architectures (Gemma 4,
    Qwen2.5, unknown equinox base — all dense ≥31B pass; all A3B MoE fine-tunes fail).
  - python_config_loader: second discriminator — fails for models with Python structural gaps: qwen3-coder:30b-1m (partial-method-completion) and quest:35b (also fails python_multifile_rename on full benchmark). These two share a gap with Python module-level/structural editing, not just method bodies.
  **north-mini-code** (Cohere, 30B MoE 3B active, Q4_K_M, ~18 GB, single RTX 4090):
  6/10 at 141 tok/s (2026-06-22). Format non-compliant on complex tasks — agentic training
  generates verbose prose/markdown preamble before code, exhausting the 8000-token budget
  before BEGIN_FILE on csv_nordic_property, python_tokenizer, and node_para_core (NO_BLOCKS).
  Token efficiency: 46.3k generated for 6 passes = 0.130 p/k (worst seen). Passes
  python_hashmap (L5) on tasks where format compliance holds. distractor_notes
  TESTS_STILL_FAIL (retrieves wrong value). Do not benchmark further without format fix.
  **gemma4:26b** (noctrex, Gemma4 A4B active, MXFP4 MOE, ~15.4 GB, single RTX 4090, Ampere+ required):
  CONFIRMED 2026-07-22 candidate run: 7/10 at 124.4 tok/s — SKIP (below 8/10 threshold).
  PASS: python_safe_div (L1), node_slugify (L2), python_lru_cache (L2), python_tokenizer (L4),
    python_expr_eval (L4), python_hashmap (L5! — first confirmed Gemma4 A4B result on this canary),
    node_para_core (L3).
  FAIL: csv_nordic_property (L3, TESTS_STILL_FAIL — generates a solution but wrong at ~2.6k tokens),
    node_csv_parser (L3, TESTS_STILL_FAIL TRUNCATED — 135s, full 16k token budget consumed by verbose
    preamble; structural, not fixable by increasing num_predict), node_paratrooper (L6 universal wall).
  Notable: python_hashmap PASS distinguishes Gemma4 A4B from many stronger-looking models (glm4-tulu:32b,
    glm4.7-flash) that also fail it. New architecture family. Both L3 CSV failures are structural gaps.
  **glm4-tulu:32b** (mradermacher, ZhipuAI GLM-4-32B dense, Tulu i1-Q4_K_M, ~19.7 GB, single RTX 4090):
  CONFIRMED 2026-07-22 candidate run: 6/10 at 40.6 tok/s — SKIP.
  PASS: python_safe_div (L1), node_slugify (L2), python_lru_cache (L2), node_csv_parser (L3),
    python_tokenizer (L4), python_expr_eval (L4).
  FAIL: csv_nordic_property (L3, TESTS_STILL_FAIL), python_hashmap (L5, TESTS_STILL_FAIL — dense
    GLM-4-32B does NOT pass the hashmap canary; Tulu fine-tune makes no difference), node_para_core (L3),
    node_paratrooper (L6 universal wall).
  Completely dominated by glm4.7-flash (29/33, 111 tok/s) despite being 4 GB larger. 4090 power
  spikes to 350W TDP throughout (dense 32B fully GPU-resident). Speed ~41 tok/s (same tier as
  qwen2.5-coder:32b-q4 and equinox:31b, but worse quality than both). Rejected.
  **qwen3-next:80b** (noctrex, 80B total / A3B active, MXFP4 MOE, 3-part ~41 GB):
  29/32 eligible at 109.3 tok/s avg on 2×24 GB tensor_split (2026-06-24, full 33-task compare).
  Speed: ~115 tok/s coding/16k, ~88 tok/s at 32k, ~26 tok/s at 128k.
  Fails node_para_core (L3), node_para_entities (L5), node_paratrooper (L6). Skill L2.
  context_256k OOM: ~41 GB weights leave insufficient KV headroom for ctx=262144 on 48 GB total;
  `cudaMalloc failed: out of memory` allocating 3072 MiB on device 0. Use `max_ctx=131072` in model
  config — bench.py emits SKIPPED_CTX instead of crashing. Already set in 2x24gb.txt and candidates.txt.
  Requires `./gpu-mode.sh multi` and `--model-timeout 1200`. Abliterated = uncensored.
  **2×24 GB compare (2026-06-24)**: qwen3.6:27b and noctrex-qwen3.6:35b both scored 32/33 at
  40.2 and 121 tok/s respectively — the only failure is node_paratrooper (L6 full from-scratch,
  universal wall). quest:35b scored 29/33 at 131.8 tok/s but Skill L1 due to python_multifile_rename
  (L2) failure. context_256k: qwen3.6:27b 26 tok/s, noctrex 75 tok/s, quest:35b 73 tok/s.
  **2026-07-23 default.txt single-GPU compare (./compare.sh --backend llama-server, llama-server 10094)**:
  8/9 models run; gpt-oss:120b SKIPPED — FileNotFoundError (GGUF not downloaded; run ./fetch-hf.sh models/default.txt first).
  | Model                | Pass/37 | Avg tok/s | Skill | Key notes |
  |---|---|---|---|---|
  | qwen3.6:27b          | 35/37 | 43.9 | L5 | context_256k TOOL_ERROR 7200s (max_ctx cap now fixed in default.txt) |
  | noctrex-qwen3.6:35b  | 34/37 | 140.9 | L2 | csv_nordic_property UNEXPECTED FAIL (was PASS 2026-06-24, 2026-07-03) |
  | qwen3.5:35b          | 33/37 | 159.9 | L2 | python_tokenizer, fastapi_endpoint, node_para_entities, paratrooper |
  | equinox:31b          | 32/37 | 40.5 | L4 | 3 SKIPPED_CTX (64k+), node_para_entities + paratrooper FAIL |
  | qwen3-30b:2507       | 31/37 | 177.3 | L2 | 2 SKIPPED_CTX (128k/256k max_ctx=65536); same failures as 2026-07-03 |
  | glm4.7-flash         | 31/37 | 131.8 | L1 | python_config_loader UNEXPECTED FAIL; context_256k TOOL_ERROR 7200s |
  | qwen2.5-coder:14b    | 27/37 | 83.2 | L2 | 7 TESTS_STILL_FAIL, 3 SKIPPED_CTX |
  | gpt-oss:20b          | 25/37 | 227.8 | <L1 | 9 NO_BLOCKS, 2 TESTS_STILL_FAIL, 1 SKIPPED_CTX |
  | gpt-oss:120b         | — | — | — | SKIPPED (FileNotFoundError: GGUF not downloaded); CONFIRMED 2026-08-11 3×24 GB: 32/34 eligible, Skill L6, perfect coding+web, full L6 stepped PASS |
  Regressions vs prior runs — CONFIRMED (re-run 2026-07-23, same binary):
  - noctrex-qwen3.6:35b csv_nordic_property: FAIL (was PASS 2026-06-24, 2026-07-03). python_config_loader PASS.
  - glm4.7-flash python_config_loader: FAIL (was PASS 2026-06-26). csv_nordic_property PASS.
  Cross-pattern: each model fails a different task — rules out task-level flakiness. llama-server 10094
  kq-mask f16 change (#25370) shifted attention in a model-architecture-specific way. Not fixable without
  a new binary or bisect. Scores on prior binary: noctrex 34/37→35/37, glm4.7-flash 31/37→32/37.
  **dotnet_sas net8→net9 fix (2026-06-21)**: both csproj files targeted `net8.0` but host
  has .NET 9.0.17 — all prior dotnet_sas failures across all models were false negatives.
  Fixed to `net9.0`; preflight.sh updated to require `.NET 9+`. Any model result predating
  this fix that shows a dotnet_sas failure should be treated as a false negative.
  **MoE weight quantization experiment (2026-06-22)**: qwen3.5:35b Q6_K vs Q4_K_M — same
  failures (python_hashmap + python_tokenizer TESTS_STILL_FAIL), 36% slower (94.5 vs ~147
  tok/s), requires dual GPU. Q4→Q6 weight precision changes nothing for MoE models; failures
  are capability/reasoning gaps, not quantization artifacts. Do not repeat for other MoE models.
- Always include the full contents of relevant files in prompts to prevent hallucinated file structure.
- **`python_hashmap` is a precision canary**: this L5 task is acutely sensitive to KV cache and
  quantization precision. With q8_0 KV or GPTQ INT4 (C4 calibration), models omit `_EMPTY = None`
  from the module-level definitions while correctly implementing the tombstone algorithm — a single
  wrong token at a precision boundary. With f16 KV (llama-server) or ollama's internal format,
  the same model passes cleanly. Use `cache_type_k=f16,cache_type_v=f16` for any 27B dense model
  whose python_hashmap fails with q8_0 KV. Do not change the task stub to paper over this.
  This precision sensitivity is specific to the qwen3.6:27b architecture (NOT all 27B models):
  qwen3.5:27b passes python_hashmap cleanly with q8_0 KV (confirmed 2026-06-27). Dense 32B
  Q4_K_M with q8_0 KV passes cleanly (qwen2.5-coder:32b-q4 confirmed 2026-06-18).
  Rule: use f16 KV only for qwen3.6:27b specifically; do not apply to other 27B models. bf16 KV has
  wider dynamic range at the same memory cost but has not been tested here — f16 has been stable and
  sufficient. Only worth trying if a model fails with f16 KV in an unexpected way. MoE models:
  Q4_K_M vs Q6_K confirmed identical scores for qwen3.5:35b (2026-06-22) — MoE weight
  quantization does not affect task outcomes; do not use higher MoE quant to fix failures.
  Also a capability discriminator: some models fail due to wrong tombstone logic regardless of
  quantization (noctrex-qwen3-coder:30b TESTS_STILL_FAIL, qwen2.5-r1:32b TESTS_STILL_FAIL,
  glm4.7-flash TESTS_STILL_FAIL, deepseek-r1:32b TESTS_STILL_FAIL, qwen3-30b:2507
  TESTS_STILL_FAIL, qwen3-coder:30b-mxfp4 TESTS_STILL_FAIL, glm4-tulu:32b TESTS_STILL_FAIL,
  qwen3-48b:a4b TESTS_STILL_FAIL, huihui-60b TESTS_STILL_FAIL,
  north-mini-code PASS, gemma4:26b PASS, gemma4:31b-qat PASS), and thinking models exhaust their
  budget in reasoning before emitting code (mellum2:12b-thinking, qwq:32b, gpt-oss:20b on this task).
  Note: glm4-tulu:32b (dense 32B) fails despite being larger than glm4.7-flash (MoE 16 GB) which
  also fails — dense scale does not fix this gap for the GLM architecture. Gemma4 A4B (MXFP4 MOE)
  passes at 15.4 GB (confirmed 2026-07-22 at f16 KV). Gemma4 dense 31B QAT also PASS (confirmed
  2026-07-24 at f16 KV) — dense Gemma 4 architecture preserves L5 precision at Q4_0.

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
run.sh              Venv setup + bench.py wrapper; sources .gpu-mode; auto-starts hwmonitor in background (--no-hwmonitor to skip); logs to logs/run-NN.log (run-latest.log symlink); BENCH_NO_LOG=1 prevents double-logging from compare.sh
gpu-mode.sh         List GPUs; toggle/set single vs. multi-GPU mode; writes .gpu-mode (gitignored, sourced by run.sh)
powerlimit.sh       GPU power cap; uniform mode (all GPUs, called by compare.sh) or --per-gpu (4090@300W, 3090@280W); WSL2-aware
compare.sh          Runs canonical 7-model set (model-timeout 1200, num-predict 8000); auto-names output by backend (results-compare.json / results-compare-ls.json); sets BENCH_NO_LOG=1 to suppress per-run log duplication; logs to logs/compare-NN.log
compare-results.sh  Merge two result JSONs and print speed summary + full task table for backend comparison
fetch-hf.sh         Download GGUF files from HuggingFace Hub based on hf: fields in models/*.txt; pre-checks repos for 404/deleted before downloading
search-hf.sh        Search HuggingFace Hub for GGUF files; suggests models/*.txt lines to paste
scout-hf.sh         Periodic HF Hub scanner; diffs against saved state (output/hf-scout-state.json); use --vllm for AWQ/GPTQ/FP8 transformers repos (state: output/hf-scout-vllm-state.json); --no-save for dry-run; --show-all to include unchanged repos
preflight.sh        Dependency checker
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
  history.py              Run history writer and header printer
logs/
  run-NN.log          Per-run output (tee from run.sh); keeps last 10; run-latest.log symlink
  compare-NN.log      Per-compare output (tee from compare.sh); compare-latest.log symlink
tests/
  test_parsing.py         Parser unit tests  →  python3 -m pytest tests/
  test_model_config.py    Model config parser unit tests
task_data/
  python_safe_div/        L1 Python pytest task (19 coding tasks total, L1–L5)
  csv_nordic_property/    L3 data task: implement solution.py against 5 000-row Nordic CSV; min_predict=8000 model_timeout=600
  context_8k/             L1 context retrieval at ~5.5k tokens (6 context tasks total)
  multihop_forward/       L3 two-hop retrieval (2 multihop tasks)
  distractor_notes/       L2 decoy-resistant retrieval
Task groups (--task-group):
  coding    19 coding tasks (L1–L5)
  web       4 web tasks (Express/FastAPI)
  l6 / para 4 stepped Paratrooper tasks (L3–L6; 'para' is alias for 'l6')
  l6_full   1 from-scratch Paratrooper task (node_paratrooper; needs --num-predict 24000)
  context   6 context retrieval tasks (8k–256k)
  multihop  3 multihop + distractor tasks
  spot      10-task candidate spot check (standard evaluation subset)
```

#### How to Run

```bash
# Install missing dependencies interactively
./install.sh

# Check all dependencies
./preflight.sh

# Full benchmark (6 models × 24 tasks)
./compare.sh

# Single model / subset of tasks
./run.sh --models qwen2.5-coder:7b --tasks python_safe_div

# Run the harness's own unit tests
python3 -m pytest tests/ -v
```

#### Deliverables Expectations

When asked to implement features:
- Provide a minimal working implementation first.
- Add at least one test for any non-trivial parser or scoring logic.
- Update `SPEC.md` / `ARCHITECTURE.md` if behavior changes.

#### vLLM backend constraints (updated 2026-07-06)

- **MoE GGUF — patched vLLM** (2026-07-06): `--quantization gguf` (ally's patched flag, not
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
- **Concurrency strength**: vLLM's primary advantage over llama-server is multi-request scheduling.
  A concurrency benchmark (1/2/4/8 simultaneous coding requests; measure aggregate tok/s, TTFT,
  per-request latency) would capture what llama-server single-request benchmarks cannot show.
- **WSL2 mirrored-mode**: startup uses log-based readiness detection; inference uses LAN IP
  fallback. See `lib/vllm_client.py` `_wait_ready()` and `_detect_connect_url()`.

#### What NOT to do

- Don't implement multi-turn autonomous "agent loops" in v1.
- Don't auto-install dependencies or mutate the user's environment.
- Don't rely on network services beyond Ollama and package restores already required by tasks.
- Don't use `shell=True` in subprocess calls.
- Don't add a `prompting.py` — prompt building lives in `tasks.py`.
