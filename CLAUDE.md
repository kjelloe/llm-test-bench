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
  **qwen3-coder:30b-1m context (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: **6/6 PASS 8k–256k**
  at 49.1 tok/s avg — 8k *82.5, 16k *77.4, 32k *58.4, 64k *36.4, 128k *26.1, 256k *13.6 tok/s.
  Context_256k at 13.6 tok/s is notably slower than quest:35b (52.4 tok/s) or noctrex (46.1 tok/s)
  at the same ctx — the "1M" long-context architecture pays a per-token overhead even at 256k.
  q8_0 KV is smaller than f16 KV but the 1M model has larger attention state per token.
  MULTIHOP (2×24 GB): **3/3 PASS at 56.1 tok/s avg** — forward *56.6 (21.2s), reverse *54.3 (27.3s),
  distractor *57.5 (28.7s). GPU1 max 70°C. max_ctx=262144 added to 2x24gb.txt.
  **devstral-small-2** (Mistral/lmstudio, dense 24B Q4_K_M, ~15 GB, single RTX 4090, q8_0 KV):
  **CODING (single GPU, CONFIRMED 2026-08-14, ls 10094)**: **17/19 at 54.6 tok/s avg**, 3:03 total.
  FAIL: csv_nordic_property (L3, TESTS_STILL_FAIL 57.5s) + node_slugify (L2, TESTS_STILL_FAIL 2.3s).
  PASS (17): all L1–L2 except node_slugify; all L3–L4 except csv_nordic; python_dijkstra (L5),
    python_hashmap (L5!). python_hashmap PASS with q8_0 KV — not architecture-specific (dense 24B
    is not the same precision-sensitive architecture as qwen3.6:27b). node_csv_parser (L3) PASS.
  Skill L1 (node_slugify L2 cap). Speed: 53.8–56.2 tok/s (narrow range, dense model).
  node_slugify failure is a genuine capability gap (regex or slug-casing logic wrong), not format.
  **CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/6 PASS 8k–128k at 26.8 tok/s avg
  (256k SKIPPED_CTX, max_ctx=131072) — ctx_8k *32.8 (5.3s), ctx_16k *31.7 (9.1s), ctx_32k *28.4
  (18.2s), ctx_64k *22.6 (43.8s), ctx_128k *18.6 (90.8s). GPU2 max 71°C. 3.6× faster at 128k
  vs single-GPU (~5.2 tok/s at 819s on 24GB → 18.6 tok/s on 2×24 GB).
  **MULTIHOP (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 3/3 PASS at 27.9 tok/s avg — forward
  *28.1 (18.9s), reverse *27.5 (29.4s), distractor *28.1 (31.1s). GPU2 max 67°C.
  Full profile: 17/19 coding + ctx 5/6 (8k–128k) + multihop 3/3. Effective Skill L1 (node_slugify cap).
  Speed on llama-server: ~54 tok/s (vs ollama ~17 tok/s — 3.2× faster).
  **qwen2.5:72b-q4** (bartowski, Qwen2.5-72B-Instruct Q4_K_M, 44.2 GB, 3×24 GB, tensor_split=1|1|1, q8_0 KV):
  CONFIRMED REJECTED 2026-08-13 spot check: **6/10 at 8.7 tok/s** — below threshold.
  PASS: python_safe_div (L1), node_slugify (L2), python_lru_cache (L2), csv_nordic_property (L3, 346s),
    node_csv_parser (L3), python_expr_eval (L4).
  FAIL: python_tokenizer (L4, TESTS_STILL_FAIL), python_hashmap (L5, TESTS_STILL_FAIL),
    node_para_core (L3, TESTS_STILL_FAIL), node_paratrooper (L6, universal wall).
  csv_nordic_property and node_csv_parser PASS confirms the prior 48 GB (4/8) failures were ctx=16384
  constraint artifacts — not capability gaps. At 72 GB VRAM with full ctx headroom, both L3 CSV tasks pass.
  python_hashmap FAIL is a genuine capability gap (not q8_0 KV precision — the q8_0 rule applies only to
  qwen3.6:27b; Qwen2.5-coder:32b passes at q8_0 KV; this instruct 72B simply cannot solve the tombstone logic).
  Speed: 8.7 tok/s avg on 3×24 GB — 6× slower than gpt-oss:120b (55 tok/s) at significantly lower quality.
  Key finding: Qwen2.5-72B-Instruct is inferior to qwen2.5-coder:32b-q4 (PERFECT 19/19) on coding tasks
  despite being 2.2× larger — coding fine-tune dominates over scale for the Qwen2.5 family.
  GPU temps (591 samples): GPU0 41-52°C, GPU1 40-62°C, GPU2 43-66°C. GGUF kept on disk; not added to any model set.
  qwen2.5-coder:32b Q4_K_M (~18.5 GB weights): CONFIRMED 2026-06-26 full 33-task on 2×24 GB:
  28/33 at 36.5 tok/s, Skill L2. CODING PERFECT (19/19) — the strongest coder tested; passes
  csv_nordic_property, node_csv_parser, and python_expr_eval (deepseek-r1:32b loops on expr_eval
  indefinitely; this model solves it cleanly). Passes node_para_turret (L4), node_para_entities (L5),
  node_para_combat (L6), multihop+distractor (3/3). FAILS: node_para_core (L3 game logic gap —
  same failure as qwen3-next:80b, quest:35b, Q5_K_M variant), node_paratrooper (L6 universal wall).
  CONTEXT CEILING: server silently caps at ctx=32768 on single-GPU, 2×24 GB, and 3×24 GB despite
  max_ctx=131072 config. CONFIRMED 2026-08-12 on 3×24 GB (72 GB VRAM): CTX_TRUNCATED on both
  context_64k (started ctx=65536) and context_128k (started ctx=131072) — server responds
  "available context size (32768 tokens)". Root cause is NOT VRAM — cap persists at 72 GB where
  KV headroom is clearly not exhausted. Cap is internal to the model/GGUF metadata (likely ROPE
  scaling config or n_ctx_train metadata limiting the effective context window regardless of server
  config). max_ctx=32768 set in all model files (24gb.txt, 2x24gb.txt, 3x24gb.txt) to match reality.
  context_64k/128k → CTX_TRUNCATED; context_256k → SKIPPED_CTX (max_ctx=131072 arch limit).
  Passes python_hashmap with q8_0 KV — the _EMPTY precision issue is specific to 27B dense models, not 32B.
  Added to models/24gb.txt (single-GPU coding tasks only) and models/2x24gb.txt (full run).
  deepseek-r1:32b Q4_K_M (~20 GB): with max_ctx=32768 scores 23/29 (26 eligible) at ~29 tok/s
  (2026-05-22). 18/19 coding at 31.4 tok/s (2026-05-24 coding run, corrected flags) —
  python_expr_eval is a structural capability gap: model enters an infinite reasoning spiral
  ("code is correct. But...") and exhausts any token budget without emitting code; not fixable
  by increasing num_predict or num_ctx. **MULTIHOP (2×24 GB, Q4_K_M, ls 10094, CONFIRMED 2026-08-13)**:
  **3/3 PASS at 18.2 tok/s avg** — forward *18.1 (57.6s), reverse *18.2 (57.0s), distractor *18.3 (44.2s).
  Thinking tokens generate extensive reasoning before answer → slower than non-thinking models at
  same generation speed. GPU1 max 67°C. ctx≥64k SKIPPED (max_ctx=32768 hard cap on single 24 GB).
  **CONTEXT (2×24 GB, Q4_K_M, ls 10094, CONFIRMED 2026-08-13)**: 4/6 — ctx_8k *23.3 (18.2s),
  ctx_16k *21.9 (24.3s), ctx_32k *18.5 (41.7s), ctx_64k *13.9 (114.2s) PASS; ctx_128k NO_BLOCKS
  (10.5 tok/s, 213.4s — thinking tokens exhaust 8000-token budget before answer at 128k prompt);
  ctx_256k SKIPPED_CTX (n_ctx_train=131072 arch limit). GPU1 max 71°C. ctx_64k generates ~1584
  tokens of reasoning (thinking-heavy) vs ~20 for non-thinking models — still answers, but barely.
  Use max_ctx=32768 in model config to unlock context_32k and multihop tasks on 24 GB.
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
  **qwen3-next:256e** (mradermacher Q4_K_M, 23.3 GB, 2×24 GB): CONFIRMED 2026-08-13 spot: **6/10, 93.1 tok/s — REJECTED**.
  PASS: python_safe_div (L1), python_lru_cache (L2), csv_nordic_property (L3!, 87.3 tok/s), python_tokenizer/expr_eval (L4),
    node_para_core (L3!, 88.7 tok/s). FAIL: node_slugify (L2, regex bug caps Skill L1), node_csv_parser (L3, quoted-comma),
    python_hashmap (L5, L5 ceiling same as A3B), node_paratrooper (L6). 256E expert routing enables csv_nordic + para_core
    (unusual for 23 GB model) but does not break L5 hashmap ceiling. node_slugify regex bug is a genuine capability gap.
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
  **CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/5 PASS 8k–128k at 56.7 tok/s avg
    (256k SKIPPED_CTX, max_ctx=131072) — ctx_8k *72.3 (6.5s), ctx_16k *58.7 (10.6s), ctx_32k *58.5 (25.3s),
    ctx_64k *49.8 (70.5s), ctx_128k *44.4 (187.8s). NOTE: tensor_split PCIe overhead reduces context speed
    vs single-GPU (73.6/63.3 tok/s at 64k/128k); single GPU is faster for this 16 GB model. GPU1 max 71°C.
  **MULTIHOP (2×24 GB, CONFIRMED 2026-08-13)**: 3/3 PASS at 70.5 tok/s avg — forward *62.4 (26.9s),
    reverse *63.9 (28.0s), distractor *85.1 (28.3s). GPU1 max 67°C.
  **qwen3-30b:2507** (unsloth, Q4_K_M A3B MoE, ~17 GB, single RTX 4090): CONFIRMED 2026-07-03
  full 37-task run: 32/37 at ~163 tok/s avg. July 2026 re-instruction fine-tune of Qwen3-30B-A3B-Instruct.
  Skill L2 (full run: python_fastapi_endpoint L3 TESTS_STILL_FAIL caps it; Skill L4 in coding-only context).
  Coding: 18/19 (python_hashmap L5 capability gap). Web: 3/4 (python_fastapi_endpoint FAIL).
  L6 stepped: passes core/turret/combat; FAILS node_para_entities (L5, step 3 gap). CONFIRMED 2026-08-13 at
    ctx=32768 (2×24 GB): entities still TESTS_STILL_FAIL (108 tok/s, 26.7s, 3/4) — genuine capability gap,
    NOT a context window issue. A3B MoE architecture cannot solve L5 game-state entities logic regardless of ctx.
    Contrast: gemma4:31b-qat (different arch + QAT) PASSES entities at ctx=32768. node_paratrooper FAIL (universal L6 wall).
  Context (single 24 GB): PASS 8k/16k/32k/64k; FAIL 128k (TOOL_ERROR 3600s, 0 tok/s — KV exhaustion at 131072 ctx);
  256k SKIPPED_CTX (arch limit 131072). Multihop (single 24 GB): 3/3 PASS at 65536 ctx (16-17 tok/s).
  **Context (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/5 PASS 8k–128k at 78.7 tok/s avg (256k SKIPPED_CTX,
    max_ctx=131072) — ctx_8k *102.6 (5.1s), ctx_16k *100.5 (10.3s), ctx_32k *74.0 (19.4s), ctx_64k *72.4 (44.0s),
    ctx_128k *43.8 (90.4s). GPU1 max 70°C. NOTE: ctx_128k slower than 2026-07-22 measurement (63.4 tok/s) —
    different binary (ls 10094 vs prior); tensor_split overhead at large context may differ between engine versions.
  context_256k SKIPPED_CTX (architecture hard limit n_ctx_train=131072, not a VRAM constraint).
  **Multihop (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 3/3 PASS at 77.7 tok/s avg — forward *72.8 (19.4s),
    reverse *82.7 (31.4s), distractor *77.7 (29.2s). GPU1 max 66°C.
  Speed: ~160-175 tok/s at coding ctx; 9.2 tok/s at 64k (KV spill single GPU).
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
  **Huihui-MoE-23B-A4B** (mradermacher, i1-Q4_K_M MoE, ~13.3 GB, single RTX 4090, no Ampere+ required):
  CONFIRMED 2026-08-12 spot check: 6/10 at 150.6 tok/s. REJECTED (below 8/10 threshold).
  PASS: python_safe_div (L1), node_slugify (L2), python_lru_cache (L2), csv_nordic_property (L3!),
    python_tokenizer (L4), node_para_core (L3).
  FAIL: node_csv_parser (TESTS_STILL_FAIL 16s — quoted-comma capability gap; quick fail, clean output format),
    python_expr_eval (NO_BLOCKS TRUNCATED 192s — 8000-token think loop, never exits to BEGIN_FILE),
    python_hashmap (NO_BLOCKS TRUNCATED 121s — same think-loop budget exhaustion),
    node_paratrooper (NO_BLOCKS TRUNCATED 206s — think loop + universal L6 wall).
  Key distinction vs A8B (24B-A8B): A4B format compliance is clean through L3 (node_slugify PASS, csv_nordic PASS);
  think-loop pathology only appears at L4+ complexity. A8B's <think> block pathology fired even on node_slugify (L2).
  A4B is an architectural improvement but still unusable above L3 on standard 8000-token budget.
  Increasing num_predict to 16000+ might fix python_expr_eval but python_hashmap is likely a capability gap
  (A8B passed python_hashmap as TESTS_STILL_FAIL — capability failure, not budget). Token efficiency 0.078 p/k.
  23B total / 4B active. Do not retry at 8000 tokens; if retried, use num_predict=16000 and verify expr_eval.
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
  PASS: node_para_core (L3) — passes where qwen3-next:80b, qwen2.5-coder:32b-q4 fail (quest:35b also PASSES node_para_core — not a universal A3B gap).
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
  Context (2×24 GB, max_ctx=131072): CONFIRMED 2026-07-26 5/6 PASS (prior binary). ctx_64k *114.7 tok/s PASS (113s);
    ctx_128k PASS (214s wall); ctx_256k SKIPPED_CTX (arch limit 131072).
    ctx_8k/16k/32k anomalous (0.7/0.4/0.3 tok/s — prefill-dominated for ~20 output tokens; actual ~88–138 tok/s from L6 run).
  **CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/6 PASS 8k–128k at 77.4 tok/s avg (256k SKIPPED_CTX, max_ctx=131072) —
    ctx_8k *85.5 (5.9s), ctx_16k *67.2 (12.7s), ctx_32k *85.8 (20.7s), ctx_64k *81.7 (41.2s), ctx_128k *66.9 (75.7s).
    GPU1 max 69°C. Prior binary ctx_64k *114.7 → ls 10094 *81.7 (-29%; consistent binary overhead for MXFP4 MoE).
  **MULTIHOP (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 3/3 PASS at 83.8 tok/s avg — forward *83.2 (20.1s),
    reverse *77.1 (24.5s), distractor *91.0 (26.1s). GPU1 max 69°C. (Prior single-GPU: ~101-103 tok/s.)
  Added to models/24gb.txt + 2x24gb.txt. f16 KV. 4090 power spikes to 350W TDP. max_ctx=32768 (single GPU), max_ctx=131072 (2×24 GB).
  agents-a1:35b (same jashepp family, different base model): FAIL csv_nordic_property (L3), 7/10, 159.8 tok/s, Skill L2 — rejected.
  Comparison: qwopus3.6 base (Qwen3.6-35B-A3B) accounts for the quality gap vs agents-a1 (unknown base).
  **equinox:31b** (jashepp, dense 31B MXFP4 Q8_0-Imatrix, ~16.4 GB, single RTX 4090, Ampere+ required):
  CONFIRMED 2026-07-04 37-task full run: 32/37 at 35.5 tok/s avg. Skill L4.
  Coding PERFECT: 19/19 (all L1–L4 + python_dijkstra + python_hashmap (L5) + node_para_combat (L6)).
  Web PERFECT: 4/4 (including python_fastapi_endpoint — field_validator + .strip()).
  Only single-24 GB model CONFIRMED with 19/19 coding + 4/4 web simultaneously. Dense ≥31B is the cutoff for fastapi_endpoint.
  FAIL: node_para_entities (L5 — CONFIRMED 2026-08-13 TESTS_STILL_FAIL at ctx=32768 on 2×24 GB — genuine capability
    gap, NOT just a context window issue. Prior NO_BLOCKS at ctx=8192 was context-induced, but at ctx=32768 the model
    generates a full implementation with wrong game logic. Hypothesis "likely PASS at 32768" was incorrect.
    PASSES combat (L6) because step-4 scaffold provides reference entities implementation.), node_paratrooper (L6 universal wall).
  Context ceiling: 32k on single 24 GB. f16 KV on dense 31B: ~5.5 GB at 32k (fits), ~11 GB at 64k + 16.4 GB weights ≈ 27.4 GB > 24 GB.
  max_ctx=32768 in 24gb.txt: context_64k/128k/256k and multihop/distractor → SKIPPED_CTX. For 64k+ context use 2×24 GB.
  **Context (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/5 PASS 8k–128k at 23.1 tok/s avg (256k SKIPPED_CTX,
    max_ctx=131072) — ctx_8k *24.4 (7.5s), ctx_16k *26.1 (20.6s), ctx_32k *22.8 (27.7s), ctx_64k *21.1 (61.9s),
    ctx_128k *20.9 (160.9s). GPU1 max 70°C. NOTE: slower than 2026-07-22 (31.1/27.3 tok/s at 64k/128k) —
    different binary; ls 10094 has higher overhead on dense MXFP4 31B context tasks.
  **Multihop (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 3/3 PASS at 22.6 tok/s avg — forward *21.2 (29.4s),
    reverse *23.3 (51.7s), distractor *23.2 (33.6s). GPU1 max 67°C. (Prior 2026-07-22: *34.3 tok/s — consistent binary delta vs context.)
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
    NOTE: the "dense ≥31B" cutoff was REVISED 2026-08-12 — gemma4:26b-qat (A4B MoE, QAT) also PASSES.
  L6 stepped (single GPU): 3/4 — core PASS, turret PASS, entities FAIL (NO_BLOCKS ctx=8192 — ctx window issue), combat PASS.
  L6 stepped (2×24 GB, --num-ctx 32768): **CONFIRMED 2026-08-13: 4/4 PASS at 32.5 tok/s avg** — core *33.6 (44.3s),
    turret *32.5 (66.4s), entities *32.2 (93.7s), combat *31.9 (140.0s). L6 chain completers (confirmed):
    gpt-oss:120b (3×24 GB), qwen3.5-122b:a10b (3×24 GB), qwopus3.6:35b (2×24 GB), gemma4:26b-qat (2×24 GB),
    gemma4:31b-qat (2×24 GB). Contrast: equinox:31b (same 31B dense tier) TESTS_STILL_FAIL entities at ctx=32768
    — genuine capability gap. qwen3-30b:2507 (A3B MoE) also FAILS entities at ctx=32768 (2026-08-13 confirmed).
    Architecture and training format (QAT, Qwen3.6 base) determine L5 game-state capability.
  **Multihop (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 3/3 PASS at 23.4 tok/s avg — forward *22.8 (28.3s),
    reverse *24.0 (50.0s), distractor *23.4 (32.2s). GPU1 max 67°C. (Prior 2026-07-25: 36.8 tok/s — binary delta.)
  Context (single 24 GB): 8k PASS (37.8 tok/s), 16k PASS (38.2 tok/s), 32k PASS (0.7 tok/s —
    bandwidth-saturated on single GPU); 64k/128k/256k SKIPPED_CTX. max_ctx=32768.
  **Context (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/5 PASS 8k–128k at 23.7 tok/s avg (256k SKIPPED_CTX,
    max_ctx=131072) — ctx_8k *24.6 (7.5s), ctx_16k *26.7 (22.0s), ctx_32k *23.5 (27.7s), ctx_64k *21.3 (61.1s),
    ctx_128k *22.3 (159.7s). GPU1 max 70°C. NOTE: slower than 2026-07-25 (*34.5/34.6/32.4/30.9/27.9) —
    ls 10094 overhead; identical speed tier to equinox:31b (23.1 tok/s avg) — both dense 31B plateau at ~23 tok/s.
    context_256k SKIPPED_CTX (architecture limit max_ctx=131072). max_ctx=131072.
  node_paratrooper (CONFIRMED 2026-08-13): TESTS_STILL_FAIL at 32.3 tok/s (97.1s, 2.9k tokens) on 2×24 GB.
    Constructor tests PASS; game loop wrong. Universal L6-full wall holds.
  Speed: ~40-43 tok/s at coding ctx — same tier as equinox:31b (~40 tok/s). f16 KV (unknown arch).
  Updated capability profile vs equinox:31b: both 31B dense, both ~42 tok/s, identical coding/web/context — BUT
    gemma4:31b-qat completes full L6 stepped chain (entities PASS at ctx=32768) while equinox:31b fails entities.
    QAT training format and Gemma4 architecture distinguish them at L5 game-state reasoning. Added to 24gb.txt + 2x24gb.txt.
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
  CONFIRMED 2026-08-11 IQ4_XS (58.4 GB, 3×24 GB, tensor_split=1|1|1): 18/19 at 54.3 tok/s avg.
  csv_nordic_property PASS (was FAIL at IQ3_XXS — CORRECTS prior assessment: this IS a precision gap,
    not a structural capability gap; IQ4_XS flips it). 144s at 20.5 tok/s (cold-start + large CSV prefill).
  node_csv_parser FAIL (TESTS_STILL_FAIL, 9.7s — quoted-comma edge case is structural, unchanged by higher quant).
  Speed: 54.3 tok/s avg (vs 96.1 tok/s at IQ3_XXS) — larger model size on same 3-GPU budget.
  IQ4_XS added to models/3x24gb.txt. REQUIRES: ./gpu-mode.sh multi and --model-timeout 1200.
  CONFIRMED 2026-08-13 L6 stepped (3×24 GB, IQ4_XS, max_ctx=32768 task default 16384): **4/4 PASS**.
    node_para_core PASS (25.4 tok/s, 54.9s), node_para_turret PASS (22.2 tok/s, 89.5s),
    node_para_entities PASS (20.3 tok/s, 149.3s — L5, key finding: A8B active params clear the entities wall
    that blocks all A3B models), node_para_combat PASS (19.5 tok/s, 218.8s).
    Joins L6 chain completers: gpt-oss:120b, qwen3.5-122b:a10b (3×24 GB),
    qwopus3.6:35b, gemma4:26b-qat, gemma4:31b-qat (2×24 GB).
    GPU temps: GPU0 max 55°C, GPU1 max 62°C, GPU2 max 65°C.
  CONFIRMED 2026-08-13 web group (3×24 GB): **4/4 PASS at 56.4 tok/s avg** (39.3s total).
    python_config_loader PASS (54.6 tok/s), bash_preflight PASS (57.7 tok/s),
    node_express_validation PASS (58.4 tok/s), python_fastapi_endpoint PASS (54.8 tok/s).
    GPU temps: GPU0 max 45°C, GPU1 max 63°C, GPU2 max 64°C.
  CONFIRMED 2026-08-13 context group (3×24 GB, max_ctx=32768): **3/3 PASS, 3 SKIPPED_CTX**.
    context_8k PASS (65.7 tok/s, 15.8s), context_16k PASS (60.3 tok/s, 29.9s),
    context_32k PASS (54.8 tok/s, 58.6s). context_64k/128k/256k SKIPPED_CTX (max_ctx=32768).
    GPU temps: GPU0 max 53°C, GPU1 max 62°C, GPU2 max 66°C.
  CONFIRMED 2026-08-13 multihop+distractor (3×24 GB, max_ctx=32768): **3/3 PASS**.
    multihop_forward PASS (53.6 tok/s, 59.4s), multihop_reverse PASS (62.1 tok/s, 64.5s),
    distractor_notes PASS (62.1 tok/s, 66.4s). GPU temps: GPU0 max 45°C, GPU1 max 62°C, GPU2 max 66°C.
  Full profile: 18/19 coding + 4/4 web + 4/4 L6 stepped + 3/3 ctx (8k–32k; 64k+ SKIPPED_CTX) + 3/3 multihop.
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
  **CODING (3×24 GB, CONFIRMED 2026-08-14, ls 10094)**: **PERFECT 19/19 at 56.1 tok/s avg, 565.5s**.
  csv_nordic_property 10.4 tok/s (275.5s — thinking + large CSV prefill). All others 20–76 tok/s.
  Temps: GPU0 max 52°C, GPU1 max 64°C, GPU2 max 64°C. Re-confirms 2026-08-11 result on ls 10094 binary.
  **PERFECT 19/19 coding + PERFECT 4/4 web** — first model to achieve both simultaneously.
  **First model to complete the full L6 stepped chain**: node_para_core (L3) + node_para_turret (L4)
    + node_para_entities (L5) + node_para_combat (L6) ALL PASS. node_paratrooper (L6-full) FAIL
    (was the universal wall at the time of this run — first broken by qwen3.8:27b on 2026-08-15,
    see that model's entry below).
  Context: context_8k PASS (62 tok/s), context_16k PASS (62 tok/s; rerun 2026-08-11 confirmed transient
    TOOL_ERROR — not a capability issue), context_32k PASS (58 tok/s), context_64k PASS (53.4 tok/s;
    CONFIRMED 2026-08-11 at max_ctx=65536). context_128k PASS (39.6 tok/s, 166s; CONFIRMED 2026-08-12
    at max_ctx=131072). context_256k SKIPPED_CTX (architecture limit n_ctx_train=131072).
  Multihop: forward/reverse/distractor all PASS (~55 tok/s).
  Speed: ~55 tok/s coding avg, 8.8-26 tok/s on para tasks (long generation), 58-73 tok/s context.
    node_para_combat: 829s at 8.8 tok/s — very long output on L6 game-state task.
    python_tokenizer: 53s at 24 tok/s. Slower than estimated 90 tok/s — model generates lengthy outputs.
  thinking=true confirmed working — no planning loops at 3×24 GB.
  Temps: GPU0 34/42/54°C (min/avg/max), GPU1 38/49/66°C, GPU2 41/56/66°C — all healthy.
  On single 24 GB: required n_cpu_moe=35 CPU offload → ~17 tok/s RAM-bound. On 3×24 GB: fully GPU-resident.
  max_ctx=131072 now set in 3x24gb.txt (was 32768→65536→131072; q8_0 KV GQA footprint confirmed smaller
  than naive estimate — context_128k fits at ~3.7 GB/GPU actual KV on 12 GB total KV across 3 GPUs).
  **qwen3.5-122b:a10b** (jamiefutch, Qwen3.5-122B-A10B MXFP4 MoE MTP-merged, ~65.1 GB, 3×24 GB required, Ampere+):
  CONFIRMED 2026-08-13 full 19-task coding: **PERFECT 19/19 at 37.4 tok/s avg**, 438.7s total.
  A10B active params break both A3B capability ceilings confirmed across all prior models:
    python_hashmap (L5) PASS at 29.0 tok/s — every A3B MoE model fails this; gpt-oss:120b also passes.
    node_para_core (L3) PASS at 18.9 tok/s (spot check) — fails for most A3B MoE models (qwen3-next:80b,
    qwen2.5-coder:32b-q4); quest:35b is an exception — PASSES node_para_core (CONFIRMED 2026-08-13, 2026-06-24 compare).
  java_word_freq (L3) PASS at 37.9 tok/s — gemma4:26b-qat (otherwise 18/19) fails this task specifically.
  csv_nordic_property PASS at 16.1 tok/s (196s — thinking tokens + large CSV prefill; same behaviour as gpt-oss:120b).
  python_expr_eval PASS at 25.2 tok/s — no infinite spiral (unlike deepseek-r1:32b which loops forever).
  node_paratrooper FAIL (TESTS_STILL_FAIL at 15.7 tok/s, 319.8s — L6-full wall, first broken by qwen3.8:27b on 2026-08-15).
  Speed: ~37–54 tok/s coding tasks (range: csv_nordic_property 16.1 tok/s long-prefill → awk_csv_stats 53.6 tok/s).
    37.4 tok/s avg is slower than gpt-oss:120b (~55 tok/s) — A10B active is more compute-heavy than gpt-oss MoE.
    Consistent with A3B→A10B scale ratio: A3B gets ~109-160 tok/s; 3.3× more active params → ~37 tok/s expected.
  thinking=true confirmed working — no planning loops at 3×24 GB (no carnice-style format pathology).
  MTP head is merged into the single GGUF file — no --spec-type flag needed; runs with standard llama-server.
    Not the same overhead mechanism as carnice:35b-mtp (which had a separate spec-decode head, 4-5× penalty).
    The merged GGUF approach results in no observed speed penalty vs. a non-MTP model of similar active params.
  q8_0 KV used — A10B MoE is not the 27B-dense architecture that has the precision issue; hashmap passes cleanly.
  Web group (CONFIRMED 2026-08-13): **4/4 PASS at 38.4 tok/s avg** — python_config_loader (39.8), bash_preflight (39.2),
    node_express_validation (35.8), python_fastapi_endpoint (38.7). Joins gpt-oss:120b + equinox:31b as only models with perfect web.
  L6 stepped (CONFIRMED 2026-08-13): **4/4 PASS at 17.4 tok/s avg**, 642.8s total. Joins gpt-oss:120b,
    gemma4:26b-qat, gemma4:31b-qat in completing the full L6 stepped chain on 3×24 GB (gpt-oss and this
    model) or 2×24 GB (gemma4 models). core *18.8 tok/s (94.8s), turret *18.2 tok/s (107.8s), entities
    *17.0 tok/s (171.8s), combat *15.7 tok/s (268.4s). Server restarted at ctx=16384 for combat step. Temps: GPU2 max 64°C.
  Context (CONFIRMED 2026-08-13): ctx_8k *51.2 tok/s, ctx_16k *46.9, ctx_32k *44.2, ctx_64k *39.7 (130.4s),
    ctx_128k *33.9 (210.4s). ctx_256k OOM — cudaMalloc failed for KV cache at 262144 ctx on GPU0.
    Context ceiling: max_ctx=131072 on 3×24 GB (65.1 GB weights leave ~6.9 GB for KV; 131072 fits, 262144 does not).
    max_ctx=131072 set in 3x24gb.txt.
  Multihop (CONFIRMED 2026-08-13): **3/3 PASS at 43.6 tok/s avg** — forward *43.4, reverse *43.6, distractor *43.7. Temps GPU2 max 66°C.
  Full capability profile (2026-08-13): **19/19 coding + 4/4 web + 4/4 L6 stepped + 5/5 context (8k–128k) + 3/3 multihop**.
    node_paratrooper FAIL (L6-full wall, first broken by qwen3.8:27b on 2026-08-15). context_256k OOM (VRAM ceiling).
  Requires ./gpu-mode.sh multi (3 GPUs) and --model-timeout 1200.
  **qwen3.8:27b** (unsloth, Qwen3.8-27B Q4_K_M, ~18.4 GB, single RTX 4090, no Ampere+ required, thinking=true, f16 KV):
  NEW Gated DeltaNet hybrid architecture — 64 layers: 16 Gated Attention (GQA 24Q/4KV/128dim) + 48 Gated DeltaNet
    (linear recurrent layers). Only 16/64 layers accumulate KV cache → ~16 KB/token at f16 vs ~128 KB/token for standard dense.
    At ctx_64k (56722 tokens): ~937 MB total KV. At max_ctx=131072: ~2.1 GB. Fixed-size recurrent state in DeltaNet layers
    (does NOT grow with context). Prefill rate: 56722 tokens in 32.2s = 1760 tok/s (confirmed 2026-08-15).
  REQUIRES llama-server build ≥ 2026-08-13 (qwen35.cpp merged commit 0d0bfcd4f, binary commit 27df9199d).
    Binary 10094 (Jul 22) predates this — rebuild with ./my-build.sh first before running qwen3.8.
  **CODING (single 24 GB, CONFIRMED 2026-08-15)**: **PERFECT 19/19 at 44.9 tok/s avg**. All tasks 43.1–46.0 tok/s.
    python_hashmap PASS (f16 KV required — same precision rule as qwen3.6:27b; q8_0 causes _EMPTY omission).
    csv_nordic_property PASS (45.6 tok/s, 70s, 6429 prompt tokens, 3.6s prefill at 1788 tok/s prefill rate).
  **WEB (single 24 GB, CONFIRMED 2026-08-15)**: **4/4 PASS at 45.5 tok/s avg** — python_config_loader (47.0),
    bash_preflight (44.1), node_express_validation (45.3), python_fastapi_endpoint (45.5).
    Dense architecture confirms fastapi PASS rule (vendor-agnostic, applies to DeltaNet hybrid too).
  **L6 STEPPED (single 24 GB, DEFAULT ctx=8192, CONFIRMED 2026-08-15)**: **4/4 PASS at 45.6 tok/s avg** —
    node_para_core (46.4, 37s), node_para_turret (45.9, 42s), node_para_entities (45.0, 64s), node_para_combat (45.3, 91s).
    DeltaNet's tiny KV footprint allows step-3 prompt (~5-7k tokens) to fit within DEFAULT ctx=8192 — unlike all other
    completers which require --num-ctx 32768. This is unique to DeltaNet's KV architecture.
  **node_paratrooper (L6 FROM-SCRATCH, CONFIRMED 2026-08-15): FIRST PASS BY ANY MODEL** — 45.5 tok/s, 103s,
    default ctx=8192 on single RTX 4090. Determinism CONFIRMED: two independent runs (det-run-A and det-run-B) produced
    identical MD5 output at temp=0, seed=1. Constructor logic correct + game loop correct — both pass cleanly.
    All previous models (including qwen3.5-122b:a10b, gpt-oss:120b, Qwen3-VL-235B-A22B Q3) had correct constructors
    but wrong game loop logic. DeltaNet's linear-recurrent layers may provide different inductive bias for
    iterative state-update reasoning. The L6-full wall is broken.
  **CONTEXT (single 24 GB, CONFIRMED 2026-08-15)**:
    ctx_8k PASS (36.9 tok/s, 5s, 7336 prompt tokens, 4.0s prefill)
    ctx_16k PASS (35.5 tok/s, 8s, 14392 prompt tokens, 7.6s prefill)
    ctx_32k PASS (36.0 tok/s, 16s, 28455 prompt tokens, 15.0s prefill)
    ctx_64k PASS (34.1 tok/s, 33s, 56722 prompt tokens, 32.2s prefill — 1760 tok/s prefill rate; VRAM delta only +64 MB)
    ctx_128k: **RE-RUN CONFIRMED 2026-08-15 (isolated, single GPU): PASS but SLOW — 10.2 tok/s, 1542.3s (25.7 min).**
      Original TOOL_ERROR (3600s timeout) was a server-sharing ARTIFACT: context bench.py (PID 525005) and multihop
      bench.py (PID 527358) shared the same llama-server on port 8080. Isolated re-run confirms this was NOT a
      capability failure — the task PASSES, but the ~64s estimate (extrapolated from the ctx_64k prefill rate) was
      badly wrong: real single-GPU throughput at 128k context is only ~10 tok/s, not the ~1760 tok/s prefill rate
      seen at 64k. Slots API showed n_prompt_tokens growing at only ~44-160 tok/s during prefill (GPU0 100% util
      but only ~106-113W of 350W TDP — memory-bandwidth-bound, not compute-bound). **CONTRADICTS the DeltaNet
      linear-scaling assumption** — throughput degrades much faster than linear between 64k and 128k on a single GPU.
      **However**: the identical task on 2×24 GB (3-GPU auto-dist, no tensor_split) PASSED context_256k — DOUBLE
      the token count — in 358.4s at 19.0 tok/s (CONFIRMED 2026-08-15), i.e. 4× faster wall-clock than the
      single-GPU 128k run despite 2× the tokens. This strongly suggests the single-GPU 128k slowdown is a
      single-GPU-specific bottleneck (bandwidth/compute contention on one card), not a fundamental architecture
      or DeltaNet scaling limit — spreading the same model across 3 GPUs (even without tensor_split explicitly
      splitting layers) relieved it. Root cause not further diagnosed; flag for anyone using qwen3.8:27b for
      128k+ context work on a single GPU — expect ~10 tok/s, not the ~34 tok/s seen at 64k.
    ctx_256k: SKIPPED_CTX on single GPU (max_ctx=131072 set as conservative limit). **CONFIRMED PASS on 2×24 GB
      (3-GPU auto-dist, max_ctx=262144, 2026-08-15): 19.0 tok/s, 358.4s.** GPU temps healthy (GPU2 max 72°C).
      DeltaNet KV at 262144 ctx fits comfortably even split across 3 GPUs without tensor_split.
  **MULTIHOP (single 24 GB, CONFIRMED 2026-08-15)**:
    multihop_forward PASS — server-sharing artifact: true speed is ~45 tok/s; 0.1 tok/s wall reflects concurrent
      ctx_128k prefill consuming GPU time (1296s wall, 1040s prefill for 29k tokens; true 1760 tok/s prefill rate
      confirms the artifact — actual test was unaffected, PASS result is valid)
    multihop_reverse PASS — same artifact, PASS result valid (1392s wall, 1094s prefill)
    distractor_notes: **RE-RUN CONFIRMED 2026-08-15 (isolated): PASS — 30.7 tok/s, 18.5s.** Original TOOL_ERROR
      (310s) was the server being KILLED when the concurrent context bench.py process finished — a test artifact
      (server death), NOT a capability failure. Isolated run passes cleanly, consistent with chain_5/cross_5 speeds.
    multihop_chain_5 PASS (44.4 tok/s, 1.3s — fresh server, true speed)
    multihop_cross_5 PASS (44.1 tok/s, 1.9s — fresh server, true speed)
  **node_paratrooper IS CONFIG-SENSITIVE ACROSS GPU SPLITS (CONFIRMED 2026-08-15) — CORRECTS earlier "cross-config
    confirmed" claim.** Three configs tested:
    - Single RTX 4090: **PASS**, 45.5 tok/s, 103s (determinism confirmed: 2 runs, identical MD5).
    - 2×24 GB, 3-GPU auto-dist (no explicit tensor_split, llama-server spreads layers across all 3 visible GPUs):
      **PASS**, 10.1 tok/s, 453.3s.
    - 2×24 GB, explicit `tensor_split=1|1` (the config now in `2x24gb.txt`): **FAIL (TESTS_STILL_FAIL)** —
      reproducibly, 2 independent runs: 28.3 tok/s/158.6s and 28.2 tok/s/159.0s (near-identical timing/speed,
      confirming this is deterministic-per-config, not a flake).
    **Interpretation:** the model has the underlying capability (2 of 3 configs pass), but the result is sensitive
    to the exact GPU partition — almost certainly a floating-point reduction-order effect from tensor-split
    aggregation flipping a close logit decision at some point in the 40-test game generation. This is a genuine
    reproducibility caveat for anyone using `tensor_split` with this model on this task, not a capability
    regression. **`models/2x24gb.txt`'s current config (`tensor_split=1|1`) will FAIL node_paratrooper** — use
    single-GPU (`24gb.txt`) if you need to reproduce the L6-full pass. GPU temps healthy across all three
    configs (max 74°C on GPU1 during the tensor_split=1|1 context_256k run).
    context_256k is NOT similarly config-sensitive: PASS on both 3-GPU auto-dist (19.0 tok/s, 358.4s) and true
    2-GPU tensor_split=1|1 (17.4 tok/s, 292.4s) — retrieval tasks with a single correct answer appear robust to
    this effect where complex multi-token game-logic generation is not.
  **EXPLICIT 3-GPU TENSOR_SPLIT=1|1|1 CONFIRMED 2026-08-16 (3×24 GB rig)**: PASS — 9.6 tok/s, 473.9s. Closely
    matches the earlier 3-GPU auto-dist result (10.1 tok/s, 453.3s) — consistent behavior. **Diffed against the
    known-good single-GPU output**: NOT byte-identical (different MD5) — genuinely different generation, e.g.
    `continue` vs nested `if` in the bomb-vs-turret check, different filter ordering, magic-number `10` vs
    `cfg.bombRadius` for off-screen culling — but still fully correct, all 40 tests pass. This is important
    nuance for the root-cause story: cross-GPU computation causes token-level divergence at ANY split (2-way
    or 3-way alike — confirmed here, the 3-way output is NOT the same as single-GPU), but whether that
    divergence lands on broken logic (2-way explicit `1|1`, confirmed FAIL) or equally-valid alternate logic
    (3-way explicit `1|1|1`, this run) is apparently probabilistic per-instance, not a property of "N-way
    splits are safe/unsafe." Treat this 3-way PASS as one confirmed data point, not a guarantee that every
    3-way run will pass — it has not been re-run for reproducibility the way the 2-way FAIL was (3 runs).
    GPU temps healthy (max 63°C). Resolves the "3-way untested" open question from 2026-08-15.
  **ROOT CAUSE CONFIRMED (CONFIRMED 2026-08-15) — diagnostic diff of the actual generated `game.js`**: re-ran
    both single-GPU (PASS, 45.5 tok/s, 103.8s — 3rd confirmation) and tensor_split=1|1 (FAIL, 28.2 tok/s, 159.2s
    — 3rd confirmation) with `--keep-workdirs` and diffed the two generated files.
    **Lines 1-268 (constructor, spawning, input handling) are byte-identical between the two runs.** The first
    divergence is at line 269 — the projectile-update loop, where the PASS output consistently names the loop
    variable `pr` while the FAIL output switches between `p` and `proj`. This stylistic/naming divergence then
    cascades autoregressively (each token conditions on the full prior sequence) through the rest of the file,
    landing on genuinely different logic for the historically hardest test (test 33, freefall-lands-on-landed
    paratrooper): the PASS version correctly checks horizontal distance only, tracks `killedLanded`, and sets
    the freefaller to `'dead'`; the FAIL version checks full 2D distance, has no kill tracking, and sets the
    freefaller to `'landed'` instead (functionally wrong — this is the exact rule every model failed on before
    qwen3.8:27b broke the wall).
    **Isolated the trigger**: ran a third config, `tensor_split=1|0` (routes 100% of the model to GPU0, but
    through the multi-GPU/tensor-split code path rather than `--single-gpu`) — result: **PASS, 45.4 tok/s,
    104.1s, and the generated `game.js` is BYTE-IDENTICAL (same MD5) to the true single-GPU output.** This
    proves the divergence is NOT caused by "using the tensor_split parameter" per se — it requires an *actual*
    cross-GPU split (real data partitioned across ≥2 physical devices, forcing cross-device floating-point
    reduction on every forward pass). A degenerate 1-GPU split through the same code path is numerically
    identical to true single-GPU. **Conclusion**: cross-GPU tensor-split introduces a tiny floating-point
    reduction-order difference (summing partial activations from multiple devices is not bit-identical to
    single-device summation) that is usually invisible, but at greedy decoding (top_k=1, confirmed via the
    /slots API) it can flip an extremely close top-1 token choice — here, apparently at an early stylistic
    decision point, which then cascades to a different (and here, wrong) implementation of a hard rule later
    in the same generation. Not a capability defect; a known class of numerical non-reproducibility in
    multi-GPU LLM inference that this benchmark happened to make visible via a binary pass/fail test.
  **2×24 GB FULL CODING+WEB+L6-STEPPED CONFIRMATION (CONFIRMED 2026-08-15, true tensor_split=1|1)**:
    ran all 19 coding + 4 web + 4 L6-stepped tasks (27 total, `--task-group coding web l6`) on the exact
    `models/2x24gb.txt` config. **27/27 PASS at 29.9 tok/s avg, 758.8s total.** Confirms the assumption
    that these groups transfer unchanged from single-GPU was correct — the config-sensitivity is specific
    to node_paratrooper (the from-scratch task with the longest, most complex generation); the 4-task
    stepped chain (shorter per-step generations) and all coding/web tasks are unaffected. GPU temps
    healthy throughout (GPU1 max 66°C).
  **OTHER L6 COMPLETER SPOT-CHECK (CONFIRMED 2026-08-15)**: tested whether other models' node_paratrooper
    FAIL is similarly config-sensitive, by re-running them on a GPU config different from their documented
    one. qwen3.6:27b (documented FAIL on 3-GPU auto-dist) **also FAILS on single GPU** (44.0 tok/s, 101s,
    TESTS_STILL_FAIL). noctrex-qwen3.6:35b (documented FAIL on 2×24 GB tensor_split=1|1) **also FAILS on
    single GPU** (122.3 tok/s, 37.5s, TESTS_STILL_FAIL). Both confirm — as expected — that these are
    genuine, large capability gaps (correct constructor, wrong game loop) rather than close-call config
    sensitivity like qwen3.8:27b's; the config-sensitivity finding is specific to qwen3.8:27b's near-miss,
    not a general property of this task. GPU temps healthy (max 67°C).
  **BINARY REGRESSION SPOT-CHECK (2026-08-15, same build used for qwen3.8:27b, commit 27df9199d)**:
    Checked whether the newer build (required for DeltaNet support) shifted results for unrelated models —
    similar to how the ls10094 kq-mask change (#25370) flipped csv_nordic_property/config_loader for other models.
    qwen3.6:27b python_hashmap: **PASS, 44.4 tok/s — no drift** (brief GPU0 power WARN 349W/350W, transient, harmless).
    noctrex-qwen3.6:35b csv_nordic_property: **still FAILS (TESTS_STILL_FAIL), 117.6 tok/s** — the kq-mask
    regression is stable across binaries, not something newly introduced. No further spot-checks needed;
    2/2 sampled results match documented baselines exactly.
  **DENSE-27B COMPARISON AT CTX_128K SINGLE GPU (CONFIRMED 2026-08-15, same binary, same hardware)**: ran
    qwen3.6:27b (standard dense attention, no DeltaNet, f16 KV) at context_128k on single GPU as a control —
    **PASS (SLOW), only 4.6 tok/s, 2275.9s (~38 min)** — actually WORSE than qwen3.8:27b's 10.2 tok/s at the
    identical context depth. **This resolves the "root cause undiagnosed" note from the earlier ctx_128k
    slowdown finding**: the single-GPU throughput collapse past 64k is NOT specific to qwen3.8:27b's DeltaNet
    architecture — it is a general pattern for large-KV models near VRAM saturation on a single 24 GB GPU
    (both models hit ~100% GPU util but only ~100-110W of 350W TDP — memory-bandwidth-bound, not compute-bound).
    If anything, DeltaNet's smaller KV footprint gives qwen3.8:27b ~2.2× better throughput than standard dense
    attention at the same context depth on the same hardware. GPU0 stayed at 45-53°C throughout (healthy).
  f16 KV required — same rule as qwen3.6:27b; q8_0 causes python_hashmap `_EMPTY` omission (density/precision boundary).
  max_ctx=131072 in 24gb.txt; max_ctx=262144 in 2x24gb.txt (DeltaNet KV fits even at 262k tokens, CONFIRMED PASS on 2×24 GB).
  Speed: ~45 tok/s consistently across all task types up to ctx_64k (narrow range 43-47 tok/s, unlike standard dense 27B
    which bandwidth-throttles to ~12 tok/s at ctx=32768 with f16 KV). **CAVEAT (CONFIRMED 2026-08-15)**: this dramatic
    DeltaNet KV benefit does NOT extend past 64k on a single GPU — ctx_128k drops to ~10 tok/s (not the ~34 tok/s
    the 8k-64k trend would predict), but this is NOT DeltaNet-specific: dense qwen3.6:27b is even slower (4.6 tok/s)
    at the same context depth on the same single-GPU setup (see DENSE-27B COMPARISON above). Both models handle the
    same context comfortably faster on 2×24 GB — the bottleneck is single-GPU VRAM-saturation-general, not
    architecture-specific.
  Skill: L6-full — first paratrooper pass on single GPU (45.5 tok/s, 103s, determinism confirmed), on 2×24 GB
    3-GPU auto-dist (10.1 tok/s, 453s), and on explicit 3×24 GB `tensor_split=1|1|1` (9.6 tok/s, 474s, CONFIRMED
    2026-08-16). **CONFIG-SENSITIVE, ROOT CAUSE CONFIRMED**: reproducibly FAILS with explicit `tensor_split=1|1`
    on 2×24 GB (3 runs, 28.2-28.3 tok/s, TESTS_STILL_FAIL) due to cross-GPU floating-point reduction
    non-determinism (confirmed via output diff) — see node_paratrooper section above. The 3-way split passing
    is a single confirmed run, not proof 3-way splits are categorically safe.
    **All other groups CONFIRMED unaffected**: 27/27 PASS (19 coding + 4 web + 4 L6-stepped) on the exact
    2×24 GB tensor_split=1|1 config. Treat the node_paratrooper pass as confirmed capability, not a
    config-independent guarantee; use single-GPU for reproduction. Added to models/24gb.txt and
    models/2x24gb.txt 2026-08-15.
  **⚠ TIEBREAKER — node_paratrooper PASS IS FILE-SPECIFIC, NOT ARCHITECTURE-GENERAL (CONFIRMED
    2026-08-20).** Tested 2 more independent Q4_K_M-class GGUF builds of this same base model on
    node_paratrooper: unsloth's own newer "Dynamic V3" requant (`Qwen3.8-27B-UD-Q4_K_M.gguf`,
    uploaded 2026-08-19, claimed >10% higher accuracy on Div-300/KLD) and bartowski's independent
    `Qwen3.8-27B-Q4_K_M.gguf`. **Both FAIL** (TESTS_STILL_FAIL, 111-112 tok/s→40.7-40.9 tok/s and
    105.2s/43.8 tok/s respectively; `python_hashmap` still PASSES on both with f16 KV — that
    precision rule is unaffected). Of 3 independently-quantized Q4_K_M-tier builds tested, **2/3
    fail** — only the original file (used for every result documented above, and which we happen
    to still have) passes, 2/2, identical MD5. **Read "first model of any size to pass
    node_paratrooper" as a property of that one specific GGUF file, not a general Qwen3.8-27B /
    Gated-DeltaNet-hybrid architecture capability** — the task appears to sit at a razor's-edge
    greedy-decoding decision that most quantizations of this model land on the FAIL side of.
    Related: the original `unsloth/Qwen3.8-27B-GGUF` repo deleted this exact file upstream on
    2026-08-19 as part of the Dynamic V3 rename (see WARNING in `models/24gb.txt`/`2x24gb.txt`);
    our local copy was briefly, accidentally deleted during this testing (an unrelated
    `hf_hub_download(local_dir=...)` call with no collision protection) and recovered via a
    pinned HF revision + SHA256 verification against the original download's `.metadata` sidecar
    — exact byte match confirmed, no data lost, but this file is now effectively irreplaceable
    (do not delete it) and the sole evidence for the PASS side of this finding. Full 3-way
    comparison table in `next-runs.md`; `qwen3.8:27b-ud` and `qwen3.8:27b-bartowski` in
    `models/candidates.txt` document both FAIL results in detail.
  **qwen3.5:27b** (bartowski, Qwen3.5-27B dense Q4_K_M, ~16 GB, 2×24 GB recommended, thinking=true, q8_0 KV):
  CONFIRMED 2026-08-13 complete profile — **Skill L6** (all task groups perfect):
  Coding: **PERFECT 19/19 at 28.4 tok/s avg** (373.6s total). python_hashmap PASS with q8_0 KV —
    confirmed 2026-06-27 original and 2026-08-13 full run. python_dijkstra PASS (27.5 tok/s). java_word_freq PASS.
    csv_nordic_property PASS, node_csv_parser PASS. ALL L1–L5 tasks pass cleanly.
  Web: **4/4 PASS at 27.8 tok/s** — python_config_loader (28.1), bash_preflight (27.8),
    node_express_validation (27.6), python_fastapi_endpoint (27.7). BREAKS "dense ≥31B" rule —
    dense 27B passes fastapi; revised rule: all dense models pass regardless of size.
  L6 stepped (2×24 GB, --num-ctx 32768): **4/4 PASS at 27.0 tok/s avg** — core *27.3 (62.8s),
    turret *27.2 (69.5s), entities *26.8 (107.2s), combat *26.6 (157.2s). Dense 27B PASSES entities
    where A3B MoE of same generation (qwen3.5:35b) FAILS — confirms gap is MoE-architectural, not generational.
  Context (2×24 GB): **6/6 PASS 8k–256k** — 8k *28.1 (7.4s), 16k *28.0 (12.3s), 32k *26.6 (25.3s),
    64k *23.6 (55.8s), 128k *21.2 (116.0s), 256k *16.4 (334.4s). Architecture supports full 262144 ctx at 2×24 GB.
  Multihop: **3/3 PASS at 26.9 tok/s avg** — forward *26.7 (26.1s), reverse *27.6 (27.5s), distractor *26.5 (29.6s).
  Full capability (2026-08-13): **19/19 + 4/4 web + 4/4 L6 + 6/6 ctx (8k–256k) + 3/3 multihop**.
    node_paratrooper FAIL (L6-full universal wall). node_para_entities PASS (dense arch advantage).
  Speed: ~28 tok/s across all task groups at 2×24 GB with q8_0 KV. Dramatically faster than qwen3.6:27b at ctx=32768
    (~12 tok/s with f16 KV) — q8_0 KV gives 2× memory efficiency at 32k ctx, preserves hashmap precision on this model.
  Use max_ctx=131072 in 2x24gb.txt. q8_0 KV (NOT f16 — f16 KV rule applies only to qwen3.6:27b).
  GPU temps (all runs 2026-08-13): GPU1 max 65-69°C — all healthy.
  **web task group results (2026-07-02/03 + 2026-07-24 + 2026-08-05 + 2026-08-12/13 + 2026-08-13, --task-group web, llama-server, 4 tasks)**:
  - **qwen3.5-122b:a10b: 4/4 at 38.4 tok/s — PASS python_fastapi_endpoint (2026-08-13). A10B MoE MTP-merged, 3×24 GB.**
  - **qwen3.5:27b: 4/4 at 27.8 tok/s — PASS python_fastapi_endpoint (2026-08-13). Dense 27B Qwen3.5 Q4_K_M, thinking. BREAKS "dense ≥31B" density cutoff — dense 27B passes. Revised: ALL dense Qwen models pass fastapi regardless of size.**
  - **qwen3.6:35b-A3B (unsloth): 4/4 at 101.1 tok/s — PASS python_fastapi_endpoint (2026-08-13). Same base as noctrex; unsloth UD-Q4_K_M passes fastapi, confirming Qwen3.6-A3B base instruction model passes regardless of quantization format.**
  - noctrex-qwen3.6:35b: 4/4 at 116.7 tok/s — PASS python_fastapi_endpoint (field_validator with .strip())
  - equinox:31b: 4/4 at 40.3 tok/s — PASS python_fastapi_endpoint (field_validator with .strip())
  - qwen2.5-coder:32b-q4: 4/4 at 33.3 tok/s — PASS python_fastapi_endpoint (field_validator with .strip())
  - gemma4:31b-qat: 4/4 at 42.2 tok/s — PASS python_fastapi_endpoint. Dense 31B QAT (Gemma 4 arch).
    Confirms dense ≥31B cutoff is architectural, not specific to Qwen base models.
  - **gemma4:26b-qat: 4/4 at 126.6 tok/s — PASS python_fastapi_endpoint (2026-08-12). A4B MoE 26B QAT
    PASSES — BREAKS established "dense ≥31B" cutoff. First MoE model to pass; first sub-31B model to pass.
    QAT training format (Q4_0 quantization-aware) is the likely differentiator — all prior A4B MoE MXFP4
    variants (gemma4:26b MXFP4) fail with Field(min_length=1). New rule: QAT Q4_0 on Gemma 4 architecture
    may enable fastapi whitespace validation regardless of active parameter count.**
  - qwen3-coder:30b-1m: 2/4 at 150.8 tok/s — FAIL python_config_loader (L2) + FAIL python_fastapi_endpoint (L3); partial-method-completion likely drops module-level env-var logic
  - quest:35b: 2/4 at 131.2 tok/s (ollama 2026-06-24) / 107.5 tok/s (llama-server 10094, 2026-08-13) — FAIL python_config_loader (L2) + FAIL python_fastapi_endpoint (L3); RL fine-tune A3B MoE — both tests confirm same failure pattern regardless of backend or speed
  - glm4.7-flash: 3/4 at 112.8 tok/s — FAIL python_fastapi_endpoint (uses Field(min_length=1), passes "   " as valid name instead of rejecting it)
  - qwen3-30b:2507: 3/4 at 162.1 tok/s — same FAIL as glm4.7-flash (same Field(min_length=1) approach)
  - qwopus3.6:35b: 3/4 at 161.8 tok/s — FAIL python_fastapi_endpoint; same cluster as glm4.7-flash + qwen3-30b:2507 despite sharing Qwen3.6-35B-A3B base with noctrex (which passes). Confirms failure is fine-tune dependent, not architecture.
  - qwen3-coder-rtpurbo:30b: 2/4 at 192.9 tok/s — FAIL python_config_loader (L2) + FAIL python_fastapi_endpoint (L3). Same 2-task failure pattern as qwen3-coder:30b-1m. Confirms RTPurbo shares the base coder model's structural Python gap.
  - qwen3.5:35b: 3/4 at 119.4 tok/s — FAIL python_fastapi_endpoint (TESTS_STILL_FAIL, 106.3 tok/s, 4.7s). PASS python_config_loader (150.5), bash_preflight (109.9), node_express_validation (110.8). Expected A3B MoE pattern (same failure cluster as glm4.7-flash + qwen3-30b:2507). GPU1 max 58°C.
  - python_fastapi_endpoint: **REVISED 2026-08-13** (qwen3.5:27b dense 27B PASS breaks "dense ≥31B"):
    PASS cluster: all dense Qwen models tested (27B, 31B, 32B); QAT training on Gemma 4 (A4B 26B+31B);
    A3B MoE standard-instruction fine-tunes (noctrex-qwen3.6:35b); A8B+ MoE (laguna, a10b, gpt-oss:120b).
    FAIL cluster: A3B MoE post-training (coder, RL, agentic) regardless of base gen (Qwen3.5/3.6);
    A4B MoE non-QAT (glm4.7-flash, gemma4:26b MXFP4); thinking does NOT help MoE models.
    Revised discriminator: dense models pass regardless of size; MoE passes only when standard-instruction
    instruct or QAT; post-trained MoE (coder/RL/agentic) uniformly fail. "Dense ≥31B" cutoff was wrong
    — the minimum bar is simply "dense architecture" (any size). Gemma4 QAT is a format exception.
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
  **gemma4:26b-qat** (lmstudio-community, Gemma4 A4B active QAT Q4_0, ~13.4 GB, single RTX 4090, no Ampere+ required):
  CONFIRMED 2026-08-11 spot 9/10 at 124.6 tok/s — PROMOTED to full 19-task coding run.
  CONFIRMED 2026-08-11 full 19-task coding: **18/19 at 129.3 tok/s avg**. Added to models/24gb.txt.
  PASS (18): all L1–L2 (node_slugify, python_safe_div, dotnet_sas, python_multifile_rename), all L3 except
    java_word_freq (python_lru_cache, python_lfu_cache, python_minheap, node_memoize_bug, python_ledger_bug,
    node_debounce, awk_csv_stats, csv_nordic_property, node_csv_parser), python_expr_eval (L4),
    python_tokenizer (L4), python_merge_intervals (L4), python_dijkstra (L5), python_hashmap (L5!).
  FAIL (1): java_word_freq (L3, TESTS_STILL_FAIL — Java word-frequency gap; 4.38s quick fail).
  node_para_core PASS (L3, spot check). node_paratrooper FAIL (L6 universal wall, spot check).
  CONFIRMED 2026-08-12 web group: **4/4 PASS at 126.6 tok/s** — including python_fastapi_endpoint.
  **BREAKS "dense ≥31B" cutoff**: A4B MoE QAT Q4_0 passes fastapi — first non-dense-≥31B model to do so.
  python_config_loader PASS (130.0 tok/s), bash_preflight PASS (131.6), node_express_validation PASS (114.8),
  python_fastapi_endpoint PASS (130.2 tok/s). QAT training format is the likely key (vs MXFP4 which fails).
  QAT vs MXFP4 comparison (same architecture, different quantization format):
  - csv_nordic_property: MXFP4 TESTS_STILL_FAIL (~2.6k tokens, wrong solution) → QAT PASS (21s, 118 tok/s)
  - node_csv_parser: MXFP4 TRUNCATED (135s, 16k budget consumed by verbose preamble) → QAT PASS (3.5s, 133 tok/s, ~465 tokens)
  - python_fastapi_endpoint: MXFP4 not tested (model rejected at 7/10) → QAT PASS (2026-08-12)
  QAT eliminates verbose-preamble behavior AND fixes csv_nordic_property AND enables fastapi validation.
  Score: 7/10 (MXFP4) → 9/10 spot → 18/19 coding → 4/4 web. First 26B A4B MoE to pass both L3 CSV + L5 hashmap + L3 fastapi.
  Speed: 129.3 tok/s coding avg, 126.6 tok/s web avg (vs MXFP4 124.4 tok/s — QAT is slightly faster at 1.3 GB smaller). No Ampere+ required.
  f16 KV (Gemma 4 architecture). max_ctx=32768 (single GPU); max_ctx=262144 in 2x24gb.txt.
  CONFIRMED 2026-08-12 L6 stepped (single GPU): 3/4 — core/turret/combat PASS; entities FAIL NO_BLOCKS
    (ctx=8192 default; step-3 prompt ~5-7k tokens leaves <1k output space — ctx window issue, NOT capability).
  CONFIRMED 2026-08-13 L6 stepped (2×24 GB, --num-ctx 32768): **4/4 at ~82 tok/s** — node_para_core PASS
    (85.9 tok/s), node_para_turret PASS (81.8 tok/s), node_para_entities PASS (80.7 tok/s),
    node_para_combat PASS (81.0 tok/s). node_paratrooper FAIL (L6 universal wall).
  CONFIRMED 2026-08-12 context (2×24 GB, tensor_split=1|1): multihop_forward 82.5 tok/s,
    multihop_reverse 82.4 tok/s, distractor_notes 83.0 tok/s. Temps healthy (GPU1 peak 66°C).
  CONFIRMED 2026-08-13 full context group (2×24 GB, 6/6 PASS): ctx_8k 74.4 tok/s, ctx_16k 79.2 tok/s,
    ctx_32k 78.8 tok/s, ctx_64k 73.7 tok/s, ctx_128k 62.7 tok/s, ctx_256k 62.4 tok/s (187.8s).
    Temps healthy (GPU1 peak 70°C). context_256k PASS is notable — same speed tier as ctx_128k despite
    double the context; architecture supports 262144 tokens cleanly at 13.4 GB weight footprint.
  Added to 2x24gb.txt. Effective Skill: L3 (java_word_freq caps; L5 hashmap/dijkstra PASS).
  Full capability profile: 18/19 coding + 4/4 web + 4/4 L6 stepped (2×24 GB) + 6/6 context 8k–256k + multihop PASS.
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
  context_256k OOM on 2×24 GB (48 GB): cudaMalloc failed on 48 GB (2026-06-27). Use max_ctx=131072
  in 2x24gb.txt — bench.py emits SKIPPED_CTX instead of crashing.
  **context_256k PASS on 3×24 GB (72 GB): CONFIRMED 2026-08-12 at 37.7 tok/s, 247s, ctx=262144.**
  Architecture supports 262144 tokens; KV footprint smaller than estimated at 72 GB split 3 ways.
  max_ctx=262144 set in 3x24gb.txt. Temps: GPU2 peak 68°C (healthy).
  **CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 5/5 PASS 8k–128k at 64.0 tok/s avg
    (ctx_256k SKIPPED_CTX, max_ctx=131072) — ctx_8k *64.4 (8.2s), ctx_16k *62.9 (14.4s),
    ctx_32k *69.6 (26.8s), ctx_64k *71.7 (53.6s), ctx_128k *51.3 (92.2s). GPU1 max 69°C.
    ls 10094 context speeds are lower than prior ollama (~115/88/26 tok/s) — different engine overhead.
  **MULTIHOP (2×24 GB, CONFIRMED 2026-08-13)**: 3/3 PASS at 67.9 tok/s avg — forward *58.0 (27.1s),
    reverse *72.3 (27.8s), distractor *73.5 (28.0s). GPU1 max 68°C.
  Requires `./gpu-mode.sh multi` and `--model-timeout 1200`. Abliterated = uncensored.
  **qwen3.6:35b-A3B (unsloth UD-Q4_K_M, 2×24 GB, thinking=true, f16 KV, CONFIRMED 2026-08-13)**:
  CODING: **17/19 at 99.7 tok/s avg, 133.3s** — FAIL: csv_nordic_property (TESTS_STILL_FAIL 95.9 tok/s,
    29.8s — kq-mask regression, same as noctrex variant), node_csv_parser (TESTS_STILL_FAIL 98.0 tok/s,
    5.4s — quoted-comma structural gap; noctrex MXFP4 passes, Q4_K_M does not at ls 10094).
    PASS: python_hashmap (L5, 97.2 tok/s — f16 KV correct for Qwen3.6-A3B MoE), python_dijkstra (L5).
  WEB: **4/4 PASS at 101.1 tok/s avg, 17.6s** — python_config_loader *102.7 (3.2s), bash_preflight
    *97.6 (3.8s), node_express_validation *102.2 (5.7s), python_fastapi_endpoint *102.0 (4.9s).
    Confirms Qwen3.6-A3B base instruction model passes fastapi (no coder/RL fine-tune penalty).
  L6 stepped: **4/4 PASS at 97.4 tok/s avg** — core *98.0 (15.5s), turret *98.1 (20.6s), entities
    *97.3 (31.4s), combat *96.2 (47.0s). GPU0 max 48°C, GPU1 max 64°C. Joins L6 chain completers.
  CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094): **6/6 PASS 8k–256k at 71.0 tok/s avg** —
    ctx_8k *78.2 (6.4s), ctx_16k *68.1 (13.1s), ctx_32k *78.8 (21.4s), ctx_64k *82.5 (43.3s),
    ctx_128k *61.4 (78.3s), ctx_256k *57.3 (185.0s). GPU1 max 70°C. max_ctx=262144 in 2x24gb.txt.
  MULTIHOP (CONFIRMED 2026-08-13): **3/3 PASS at 86.7 tok/s avg** — forward *87.4 (20.9s),
    reverse *94.0 (22.9s), distractor *78.7 (24.4s). GPU1 max 70°C.
  Full profile: 17/19 coding + 4/4 web + 4/4 L6 stepped + 6/6 ctx (8k–256k) + 3/3 multihop = Skill L6.
  qwen3.5:35b (same A3B MoE, Qwen3.5 generation) FAILS entities (CONFIRMED 2026-08-13 at
  --num-ctx 32768 --num-predict 16000: TESTS_STILL_FAIL 30.5s at 103.4 tok/s — genuine capability gap).
  **qwen3.5:35b context (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: **6/6 PASS 8k–256k at 77.2 tok/s avg** —
    ctx_8k *91.4 (6.5s), ctx_16k *99.3 (10.1s), ctx_32k *77.2 (20.4s), ctx_64k *72.0 (44.4s),
    ctx_128k *67.4 (79.2s), ctx_256k *55.7 (188.3s). max_ctx=262144 in 2x24gb.txt. GPU1 max 71°C.
    MoE retrieval speed at 256k: 55.7 tok/s — between noctrex Qwen3.6 (46.1) and quest:35b (52.4).
    Architecture supports 262144 context cleanly without KV exhaustion at 2×24 GB.
  **qwen3.5:35b multihop (2×24 GB, CONFIRMED 2026-08-13)**: **3/3 PASS at 93.4 tok/s avg** —
    forward *92.3 (21.1s), reverse *103.3 (22.3s), distractor *84.5 (22.3s). GPU1 max 70°C.
  **qwen3.5:27b (dense 27B, Qwen3.5 generation) PASSES all 4 L6 tasks (CONFIRMED 2026-08-13 at
  --num-ctx 32768: 4/4 PASS, 27.0 tok/s avg — core *27.3 (62.8s), turret *27.2 (69.5s), entities
  *26.8 (107.2s), combat *26.6 (157.2s). Joins L6 chain completers (10th model).**
  KEY ARCHITECTURAL FINDING: the entities capability gap is **A3B MoE architecture-specific**, NOT
  a Qwen3.5 generation issue. Dense Qwen3.5:27b passes entities; A3B MoE Qwen3.5:35b fails.
  The MoE sparse activation (A3B = 3B active parameters) lacks the entity management reasoning
  capability that dense models of similar or even smaller size possess.
  **noctrex-qwen3.6:35b L6 stepped (CONFIRMED 2026-08-13, 2×24 GB, MXFP4 MoE)**:
  **4/4 PASS at 90.8 tok/s avg** — core *91.5 (16.3s), turret *91.6 (21.9s), entities *89.8 (34.0s),
  combat *90.2 (49.3s). Total 2m1s. GPU0 max 50°C, GPU1 max 64°C, GPU2 max 46°C.
  Joins L6 chain completers. The 2026-07-23 default compare entities FAIL was single-GPU with default
  ctx=8192 — step-3 prompt fills ctx before output. At --num-ctx 32768 on 2×24 GB, PASS. The kq-mask
  f16 regression in llama-server 10094 affects csv_nordic_property (TESTS_STILL_FAIL) but NOT the
  L6 stepped chain. Note: no thinking flag in noctrex config — MXFP4 model does not set thinking=true.
  CONTEXT (2×24 GB, CONFIRMED 2026-08-13): **6/6 PASS 8k–256k at 68.0 tok/s avg** — ctx_8k *62.7 (7.2s),
    ctx_16k *79.3 (10.0s), ctx_32k *82.2 (19.9s), ctx_64k *69.7 (42.4s), ctx_128k *67.7 (75.7s),
    ctx_256k *46.1 (182.5s). ls 10094 confirmed all 6 pass. GPU1 max 71°C.
  MULTIHOP (CONFIRMED 2026-08-13): **3/3 PASS at 83.7 tok/s avg** — forward *80.8 (20.5s),
    reverse *97.2 (23.1s), distractor *73.0 (25.3s). GPU1 max 68°C.
  L6 completers (2×24 GB): noctrex-qwen3.6:35b, qwen3.6:35b-A3B (unsloth), qwopus3.6:35b,
    gemma4:26b-qat, gemma4:31b-qat. All use --num-ctx 32768 explicitly for L6 tasks.
  **qwen3.6:27b L6 stepped (CONFIRMED 2026-08-13, 3-GPU auto, f16 KV, --num-ctx 32768)**:
  **4/4 PASS** — core *13.4 (101s), turret *10.1 (179s), entities *12.8 (217s), combat *9.6 (417s,
  --model-timeout 600). Very slow due to dense 27B attention at ctx=32768 (O(n) bandwidth-bound).
  GPU0 max 52°C, GPU1 max 62°C, GPU2 max 65°C. 9th L6 completer. NOTE: dense 27B uses f16 KV
  (required for python_hashmap); at 32k ctx this is ~3.75 GB KV which causes 3×+ slowdown vs 8k ctx.
  node_para_combat needs --model-timeout 600 (417s at 9.6 tok/s — default 300s too short).
  L6 completers (single 24 GB, compact MoE): glm4.7-flash (CONFIRMED 2026-07-23 compare, ~111 tok/s,
    generates concise code in steps 1-2, leaving short step-3 prompt that fits in ctx=8192).
  **quest:35b L6 stepped (CONFIRMED 2026-08-13, 2×24 GB, 3-GPU auto-dist, f16 KV, --num-ctx 32768)**:
  **4/4 PASS** — core *24.9 (56.8s), turret *14.6 (139s), entities *12.1 (223s), combat *10.5 (383s,
  --model-timeout 600). Very slow due to 3-GPU auto-distribution (no tensor_split in config).
  **tensor_split=1|1 CONFIRMED 2026-08-13: 97.3 tok/s avg** (7/9 spot: all L1–L4 coding tasks PASS,
  csv_nordic_property PASS 95.2 tok/s, node_csv_parser FAIL as expected, node_para_core PASS 98.2 tok/s).
  11th L6 completer. quest:35b is almost certainly Qwen3.6 A3B base (entities PASS = strong Qwen3.6
  discriminator; Qwen3.5 A3B fails entities). RL training originally introduced python_multifile_rename FAIL
  (with ollama 2026-06-24) but this task PASSES with llama-server 10094 (kq-mask change reversed the gap).
  **python_hashmap REGRESSION (llama-server 10094)**: PASS with ollama (2026-06-24) → TESTS_STILL_FAIL
  with llama-server 10094 (2026-08-13, 6.89s, 686 tokens). Reverse swap: python_multifile_rename now PASSES,
  python_hashmap now FAILS — kq-mask f16 change shifted quest:35b's attention in both directions.
  **CONFIRMED 2026-08-13 full 19-task coding: 17/19 at 100.0 tok/s** (failures: node_csv_parser + python_hashmap).
  **CONTEXT (2×24 GB): 6/6 PASS 8k–256k** — ctx_8k *83.5 (6.7s), ctx_16k *91.9 (10.4s), ctx_32k *86.7 (21.2s),
    ctx_64k *69.6 (44.2s), ctx_128k *66.4 (80.2s), ctx_256k *52.4 (190.3s). max_ctx=262144 set in 2x24gb.txt.
    MoE efficiency (A3B active): ctx_256k at 52.4 tok/s vs qwen3.5:27b dense at 16.4 tok/s — 3× faster for long context.
  **MULTIHOP: 3/3 PASS at 89.8 tok/s avg** — forward *80.2 (24.9s), reverse *91.6 (24.3s), distractor *97.5 (22.6s). (CONFIRMED 2026-08-13, ls 10094)
  **WEB: 2/4 at 107.5 tok/s** — bash_preflight PASS, node_express_validation PASS, python_config_loader FAIL,
    python_fastapi_endpoint FAIL. Expected: RL fine-tune A3B MoE fails both config_loader and fastapi
    (same failure cluster as all other post-trained A3B MoE models). Matches prior ollama result.
  **Full capability (2026-08-13): 17/19 coding + 2/4 web + 4/4 L6 stepped + 6/6 ctx (8k–256k) + 3/3 multihop. (all groups CONFIRMED ls 10094)**
    Skill L6 (from L6 stepped chain). node_paratrooper FAIL (universal L6 wall). python_hashmap FAIL (ls 10094 regression).
  tensor_split=1|1 added to 2x24gb.txt model config — prior missing config was root cause of 3-GPU auto-dist.
  Full L6 chain completer list (confirmed with current task definition):
  - **🏆 node_paratrooper (L6-full) FIRST PASS: qwen3.8:27b, 2026-08-15, ~45 tok/s, single 24 GB, default ctx=8192**
    (PASS also on 2×24 GB / 3-GPU auto-dist, no tensor_split: 10.1 tok/s, 453.3s — not a single-GPU-only fluke.
    **BUT CONFIG-SENSITIVE**: reproducibly FAILS with explicit tensor_split=1|1 on 2×24 GB (3 runs: 28.3/158.6s,
    28.2/159.0s, 28.2/159.2s tok/s, TESTS_STILL_FAIL every time). **ROOT CAUSE CONFIRMED via output diff
    (2026-08-15)**: generated `game.js` is byte-identical between single-GPU and `tensor_split=1|0` (a
    degenerate split that keeps 100% on one GPU) — proving true cross-GPU computation (not "using
    tensor_split" per se) is the trigger. Diverges from single-GPU output at line 269 (a naming choice),
    cascades autoregressively, lands on wrong logic for the hardest game rule (test 33) by the end. This is
    floating-point reduction-order non-determinism in cross-GPU aggregation, not a capability regression.
    Use single-GPU to reproduce reliably. See qwen3.8:27b's full entry above for complete diagnostic detail.)
  - 3×24 GB: gpt-oss:120b (~55 tok/s), qwen3.5-122b:a10b (~17 tok/s), laguna-s-2.1:118b-iq4 (~21 tok/s)
  - 2×24 GB (--num-ctx 32768): noctrex-qwen3.6:35b (~91 tok/s), qwen3.6:35b-A3B unsloth (~97 tok/s),
      qwopus3.6:35b (~123 tok/s), gemma4:26b-qat (~82 tok/s), gemma4:31b-qat (~32 tok/s),
      qwen3.6:27b (~12 tok/s, f16 KV, model-timeout 600 for combat),
      qwen3.5:27b (~27 tok/s, q8_0 KV),
      quest:35b (~97 tok/s CONFIRMED with tensor_split=1|1; model-timeout 600 for combat at ctx=32768)
  - 1×24 GB (default ctx): glm4.7-flash (~111 tok/s)
  - 1×24 GB (default ctx, **L6-full — paratrooper PASS**): qwen3.8:27b (~45 tok/s, f16 KV, new binary ≥ 2026-08-13)
  Note: qwen3.6:27b's ~12 tok/s for L6 tasks makes it practical only as a capability test.
  Note: qwen3.5:27b at ~27 tok/s is faster for L6 despite older Qwen generation — q8_0 KV vs f16.
  Entities gap is A3B MoE specific: Qwen3.5 A3B MoE (qwen3.5:35b, qwen3-30b:2507,
    qwen3-coder:30b-1m CONFIRMED FAIL 2026-08-13 at ctx=32768, 92.1 tok/s 30.5s) FAIL;
    dense Qwen3.5 (qwen3.5:27b) PASS; all Qwen3.6 variants PASS; Gemma4 QAT and GLM4.7 PASS;
    quest:35b (likely Qwen3.6 A3B RL fine-tune) PASS 2026-08-13.
    qwen3-coder:30b-1m confirms coder fine-tunes of Qwen3.5 A3B base inherit the entities gap.
    core/turret/combat PASS for Qwen3.5 A3B MoE — only entities (step 3) FAIL.
  **CONTEXT (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 6/6 PASS 8k–256k at 24.6 tok/s avg —
  ctx_8k *29.0 (9.0s), ctx_16k *19.6 (18.3s), ctx_32k *29.1 (29.8s), ctx_64k *26.6 (63.9s),
  ctx_128k *24.3 (133.7s), ctx_256k *19.0 (376.0s). GPU2 max 72°C. Prior 2026-06-24 256k speed
  was 26 tok/s (prior binary); ls 10094 shows 19.0 tok/s — consistent binary overhead pattern.
  **MULTIHOP (2×24 GB, CONFIRMED 2026-08-13, ls 10094)**: 3/3 PASS at 29.7 tok/s avg — forward
  *29.9 (29.6s), reverse *29.6 (41.1s), distractor *29.7 (41.5s). GPU2 max 67°C.
  **2×24 GB compare (2026-06-24)**: qwen3.6:27b and noctrex-qwen3.6:35b both scored 32/33 at
  40.2 and 121 tok/s respectively — the only failure is node_paratrooper (L6 full from-scratch,
  universal wall). quest:35b scored 29/33 at 131.8 tok/s but Skill L1 due to python_multifile_rename
  (L2) failure. context_256k: qwen3.6:27b 26 tok/s (prior binary), noctrex 75 tok/s, quest:35b 73 tok/s.
  **2026-07-23 default.txt single-GPU compare (./compare.sh --backend llama-server, llama-server 10094)**:
  8/9 models run; gpt-oss:120b SKIPPED — FileNotFoundError (GGUF not downloaded; run ./fetch-hf.sh models/default.txt first).
  | Model                | Pass/37 | Avg tok/s | Skill | Key notes |
  |---|---|---|---|---|
  | qwen3.6:27b          | 35/37 | 43.9 | L5 | context_256k TOOL_ERROR 7200s (max_ctx cap now fixed in default.txt); L6 entities CONFIRMED PASS (--num-ctx 32768, 2026-08-13, 4/4 stepped chain, ~12 tok/s, model-timeout 600) |
  | noctrex-qwen3.6:35b  | 34/37 | 140.9 | L2 | csv_nordic_property UNEXPECTED FAIL (was PASS 2026-06-24, 2026-07-03); entities FAIL was ctx=8192 issue (CONFIRMED PASS at --num-ctx 32768 2×24 GB, 2026-08-13) |
  | qwen3.5:35b          | 33/37 | 159.9 | L2 | python_tokenizer, fastapi_endpoint, node_para_entities, paratrooper; entities CONFIRMED genuine capability gap at --num-ctx 32768 2026-08-13 (TESTS_STILL_FAIL, not ctx issue) |
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
- **CPU-MoE paging (llama-server)**: MoE models slightly over VRAM capacity can run via mmap paging.
  Flags: `-ngl 999 --n-cpu-moe N --no-repack`. Keeps expert FFN tensors of the first N layers
  CPU-resident (mmap'd, page-cached in RAM); attention stays on GPU.
  **MUST omit `no_mmap` from the model config** — it forces full RAM residency and defeats paging.
  Model config entries using this technique: no `no_mmap`, add `n_cpu_moe=N,no_repack`.
  (Both params pass through the existing underscore→hyphen converter in llama_server_client.py; no
  code changes needed.)
  Speed rule of thumb on 86 GB DDR5 (~90 GB/s): ~53 tok/s for A3B active, ~10 tok/s for A15B.
  Best use case: model ≤4 GB over 72 GB VRAM limit → small N (4–8 layers) sheds just enough
  expert weight, leaving throughput near GPU speeds.
  Dense models gain nothing — all weights touched every token = disk thrash.
  **n_cpu_moe calibration lesson (gpt-oss-120b Fable-5, 2026-08-12)**: initial estimate of
  n_cpu_moe=8 was 4× too low. With tensor_split=1|1|1, the KV cache is also split across GPUs —
  the model weights pack each GPU to the point that even 51 MiB of KV cache on GPU2 fails.
  OOM persisted up to n_cpu_moe=24; n_cpu_moe=30 was the first working value (32% of layers).
  Rule: for a model 3 GB over VRAM, expect to offload ~30% of MoE layers, not ~8%.
  gpt-oss-120b Fable-5 Q5_0 (75.1 GB): CONFIRMED REJECTED 2026-08-12. Speed 7.8–9.2 tok/s
  (6–7× slower than GPU-resident base at 55 tok/s). node_paratrooper STILL FAILS — Fable-5
  distillation does not fix the L6 universal wall. See candidates.txt for full results.
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
  quest:35b TESTS_STILL_FAIL with llama-server 10094 f16 KV (was PASS with ollama 2026-06-24 — llama-server 10094 kq-mask regression specific to this model; entities PASS still confirms Qwen3.6 base),
  north-mini-code PASS, gemma4:26b PASS, gemma4:31b-qat PASS, qwen3.5-122b:a10b PASS), and thinking models exhaust their
  budget in reasoning before emitting code (mellum2:12b-thinking, qwq:32b, gpt-oss:20b on this task).
  Note: glm4-tulu:32b (dense 32B) fails despite being larger than glm4.7-flash (MoE 16 GB) which
  also fails — dense scale does not fix this gap for the GLM architecture. Gemma4 A4B (MXFP4 MOE)
  passes at 15.4 GB (confirmed 2026-07-22 at f16 KV). Gemma4 dense 31B QAT also PASS (confirmed
  2026-07-24 at f16 KV) — dense Gemma 4 architecture preserves L5 precision at Q4_0.
  qwen3.5-122b:a10b PASS (confirmed 2026-08-13, q8_0 KV) — A10B active-param tier clears the ceiling
  that blocks all A3B models. gpt-oss:120b also passes (thinking model, q8_0 KV).

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
  multihop_chain_5/       L4 5-hop config inheritance (correct answer: 90; sibling distractor: 45; top-level distractor: 30)
  multihop_cross_5/       L4 5-doc cross-reference (correct: oncall-emea-w-high; criticality distractor: oncall-emea-w-crit)
Task groups (--task-group):
  coding    19 coding tasks (L1–L5)
  web       4 web tasks (Express/FastAPI)
  l6 / para 4 stepped Paratrooper tasks (L3–L6; 'para' is alias for 'l6')
  l6_full   1 from-scratch Paratrooper task (node_paratrooper; needs --num-predict 24000)
  context   6 context retrieval tasks (8k–256k)
  multihop  5 multihop + distractor tasks (2-hop forward/reverse, 1 distractor, chain_5, cross_5)
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

# See what tasks exist — id, difficulty, group, description — before picking one to export
python3 bench.py --list-tasks

# Export a task as a shareable, self-contained package (TASK.md + PROMPT.txt + starting files)
# for another coding agent to attempt directly — no model/backend needed for this mode.
python3 bench.py --export-task node_paratrooper --export-dir ~/share/l6-full-challenge

# Same, to a scratch dir — the L6-full task, the hardest in the benchmark (see CLAUDE.md above)
python3 bench.py --export-task node_paratrooper --export-dir /tmp/mytestdir

# Any other task works the same way — e.g. the L5 precision-canary task
python3 bench.py --export-task python_hashmap --export-dir /tmp/mytestdir-hashmap

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
