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
    Needs 8000+ for L2+ tasks; compare.sh now uses 8000 which should fix these.
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
  qwen2.5-coder:32b Q4_K_M (~20 GB weights) leaves only ~4 GB for KV on 24 GB — ctx=32768
  causes TOOL_ERROR timeout (300s) on context_32k and multihop tasks; 15/15 coding tasks
  pass cleanly at ~36 tok/s. Large-context tasks require a true 32 GB card.
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
  phi4-reasoning-plus:14b (thinking, ~9 GB): ~58 tok/s but INCOMPATIBLE with this benchmark.
  Loops in a reasoning planning phase ("I'll produce the file content with the modifications"
  repeated indefinitely) and never emits BEGIN_FILE regardless of num_predict — confirmed at
  both 4800 and 12000 tokens (0/13 on targeted re-run at 12k). Format compliance issue: the
  model was trained to emit answers inline, not in structured file blocks. Do not benchmark.
  llama4-scout:17b (MoE 17B active / 109B total, ~60 GB hybrid): ~3.3 tok/s — fully
  CPU-bound on 24 GB VRAM; 109 GB weights live in RAM. Quality is high (19/24) but throughput
  is impractical. csv_nordic_property times out (model_timeout=600s at 3.3 tok/s ≈ 2000 max
  tokens). context_128k passes SLOW (1216s). Needs 64 GB+ VRAM to be GPU-resident and fast.
- Always include the full contents of relevant files in prompts to prevent hallucinated file structure.
- **`python_hashmap` is a precision canary**: this L5 task is acutely sensitive to KV cache and
  quantization precision. With q8_0 KV or GPTQ INT4 (C4 calibration), models omit `_EMPTY = None`
  from the module-level definitions while correctly implementing the tombstone algorithm — a single
  wrong token at a precision boundary. With f16 KV (llama-server) or ollama's internal format,
  the same model passes cleanly. Use `cache_type_k=f16,cache_type_v=f16` for any 27B dense model
  whose python_hashmap fails with q8_0 KV. Do not change the task stub to paper over this.
  **f16 KV trade-off at 128k context (confirmed 2026-05-28, qwen3.6:27b)**: f16 KV causes heavy
  VRAM spill at ctx=131072 — 6.8 tok/s (1657s, SLOW) vs ~15-18 tok/s with q8_0 KV. The 2.7×
  speed penalty at 128k is the real cost of the f16 requirement. context_128k still passes within
  the 3600s task timeout but triggers the SLOW flag. Accept this trade-off; do not switch to q8_0.

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
run.sh              Venv setup + bench.py wrapper
compare.sh          Runs canonical 9-model set (model-timeout 1200, num-predict 8000); auto-names output by backend (results-compare.json / results-compare-ls.json)
compare-results.sh  Merge two result JSONs and print speed summary + full task table for backend comparison
fetch-hf.sh         Download GGUF files from HuggingFace Hub based on hf: fields in models/*.txt
search-hf.sh        Search HuggingFace Hub for GGUF files; suggests models/*.txt lines to paste
preflight.sh        Dependency checker
lib/
  tasks.py                Task definitions, prompt builder, subprocess helpers
  ollama_client.py        Ollama /api/chat client
  llama_server_client.py  LlamaServerManager (spawn/stop llama-server) + chat() for OpenAI-compatible API
  vllm_client.py          VLLMManager (spawn/stop vllm serve) + chat() for OpenAI-compatible API
  model_config.py         Parse models/*.txt 3-field format → ModelConfig dataclasses
  parsing.py              BEGIN_FILE/END_FILE parser + allow-list validator
  reporting.py            Comparison table (paginated), failure detail, JSON writer
  hw_snapshot.py          GPU/CPU/RAM snapshot (nvidia-smi, /proc/cpuinfo, /proc/meminfo)
  gpu_monitor.py          pynvml GPU telemetry
  history.py              Run history writer and header printer
tests/
  test_parsing.py         Parser unit tests  →  python3 -m pytest tests/
  test_model_config.py    Model config parser unit tests
task_data/
  python_safe_div/        L1 Python pytest task (19 coding tasks total, L1–L5)
  csv_nordic_property/    L3 data task: implement solution.py against 5 000-row Nordic CSV; min_predict=8000 model_timeout=600
  context_8k/             L1 context retrieval at ~5.5k tokens (6 context tasks total)
  multihop_forward/       L3 two-hop retrieval (2 multihop tasks)
  distractor_notes/       L2 decoy-resistant retrieval
```

#### How to Run

```bash
# Install missing dependencies interactively
./install.sh

# Check all dependencies
./preflight.sh

# Full benchmark (9 models × 33 tasks)
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

#### vLLM backend constraints (2026-05-27, vLLM with GGUF)

- **MoE GGUF not supported**: `--load-format gguf` fails for any MoE / A3B model with
  `Failed to map GGUF parameters: model.layers.X.mlp.experts.*`. Affects qwen3-coder:30b,
  qwen3.5:35b-A3B, qwen3.6:35b-A3B, noctrex. Dense models (14B, 32B, 70B) work fine.
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

- **New model candidates (scout 2026-05-27)**:
  - `Qwen3-Coder-Next` (Qwen/Qwen3-Coder-Next-GGUF) — BENCHMARKED 2026-05-28: **19/19 PERFECT**
    at 16.6 tok/s. ACTUAL SIZE: ~46 GB (4 shards: 15+14+14+3.3 GB) — ~72B dense; the "14.5 GB"
    estimate was shard 1 only. RAM-bound on 24 GB (52% VRAM). Not replacing qwen3-coder:30b-1m
    (9× faster at 150 tok/s). HIGH VALUE for dual-GPU: fully resident on 48 GB → ~35-40 tok/s.
    Added to default.vllm dual-GPU queue (commented).
  - `gemma-4-31B` (unsloth/gemma-4-31B-it-GGUF, ~17.1 GB Q4_K_M) — BENCHMARKED 2026-05-28:
    **18/19**, 34.6 tok/s. FAILS node_csv_parser (ESM syntax: `export function` in CJS context —
    model output format bias, not capability gap). PASSES csv_nordic_property — confirms
    dense-beats-MoE pattern in Gemma 4 generation (gemma4:26b MoE fails csv_nordic at 110 tok/s).
    Peak skill L5 (passes dijkstra + hashmap); Skill L2 due to node_csv_parser L3 wall.
    Not added to default.txt (18/19 at ~35 tok/s doesn't displace any current model).
  - Devstral-Small-2507/2505 — OLDER versions (July/May 2025); current is 2512. Skip.
  - Devstral-2-123B (46.5 GB) — needs dual GPU; note for when hardware arrives.
  - Qwen3.6-27B-MTP (unsloth) — skip; MTP harms determinism (same as carnice pattern).

#### What NOT to do

- Don't implement multi-turn autonomous "agent loops" in v1.
- Don't auto-install dependencies or mutate the user's environment.
- Don't rely on network services beyond Ollama and package restores already required by tasks.
- Don't use `shell=True` in subprocess calls.
- Don't add a `prompting.py` — prompt building lives in `tasks.py`.
