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
- `num_predict` default is 400 for simple/instruct models. Use 4800+ for thinking models
  (qwen3.5, gpt-oss:120b, deepseek-r1, etc.) — their reasoning tokens consume the budget
  before the answer. `compare.sh` sets `--num-predict 4800` explicitly; 2400 was too few for
  qwen3.5:35b on basic tasks; 1200 was too few for gpt-oss:120b on complex tasks (CSV parser
  ran out mid-reasoning). Note: gpt-oss:20b and gemma4:26b are NOT thinking models — do not
  mark them `thinking` in model files; the "After your reasoning" prefix causes planning loops.
  - **gpt-oss:20b "semi-thinking"**: generates verbose reasoning in plain text output (not
    `reasoning_content`) on L2+ tasks; exhausts 4800 token budget before BEGIN_FILE on
    python_lru_cache, python_lfu_cache, python_expr_eval. Needs 8000+ for those tasks.
    Adding `thinking` does NOT help — it causes a different planning loop. It is correctly
    left without the `thinking` flag.
  - **gemma4:26b verbose preamble**: generates a long task description + approach summary
    before BEGIN_FILE regardless of the system prompt; exhausts 4800 tokens on complex tasks
    (node_csv_parser, python_lru_cache, python_tokenizer, multihop_forward, csv_nordic_property).
    Needs 8000+ for L2+ tasks.
  - **qwen3.5:35b over-reasoning**: even python_hashmap at min_predict=16000 is exhausted
    by reasoning alone (wall 100s × 158 tok/s ≈ all 16000 tokens); consider 24000 for that task.
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
  devstral-small-2 (24B dense) similarly spills at ~4.0 tok/s (480s) at ctx=131072 on 24GB
  — wall_time_budget_s=300 flags it as PASS_BUT_SLOW.
  qwen2.5-coder:32b Q4_K_M (~20 GB weights) leaves only ~4 GB for KV on 24 GB — ctx=32768
  causes TOOL_ERROR timeout (300s) on context_32k and multihop tasks; 15/15 coding tasks
  pass cleanly at ~36 tok/s. Large-context tasks require a true 32 GB card.
  deepseek-r1:32b Q4_K_M (~20 GB): same KV-pressure pattern; 16/24 on 24 GB at ~32 tok/s;
  coding tasks pass, ctx≥32k fails. Viable for coding-only on 24 GB; true 32 GB needed for
  large-context tasks.
  qwq:32b Q5_K_M (~22 GB): effectively unusable on 24 GB — KV thrashing reduces throughput
  to ~6 tok/s; 11/24 tasks pass. Server silently caps max_ctx=65536 → 32768 when VRAM is
  exhausted. Needs true 32 GB to be useful. Use `max_ctx=32768` in model config to avoid
  CTX_TRUNCATED errors on 24 GB.
- Always include the full contents of relevant files in prompts to prevent hallucinated file structure.

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
compare.sh          Runs canonical 6-model set (model-timeout 1200, num-predict 2400); auto-names output by backend (results-compare.json / results-compare-ls.json)
compare-results.sh  Merge two result JSONs and print speed summary + full task table for backend comparison
fetch-hf.sh         Download GGUF files from HuggingFace Hub based on hf: fields in models/*.txt
search-hf.sh        Search HuggingFace Hub for GGUF files; suggests models/*.txt lines to paste
preflight.sh        Dependency checker
lib/
  tasks.py                Task definitions, prompt builder, subprocess helpers
  ollama_client.py        Ollama /api/chat client
  llama_server_client.py  LlamaServerManager (spawn/stop llama-server) + chat() for OpenAI-compatible API
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
  python_safe_div/        L1 Python pytest task (13 coding tasks total, L1–L5)
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

#### What NOT to do

- Don't implement multi-turn autonomous "agent loops" in v1.
- Don't auto-install dependencies or mutate the user's environment.
- Don't rely on network services beyond Ollama and package restores already required by tasks.
- Don't use `shell=True` in subprocess calls.
- Don't add a `prompting.py` — prompt building lives in `tasks.py`.
