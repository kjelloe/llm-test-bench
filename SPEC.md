### Product Spec: Local LLM Benchmark Harness (Ollama)

#### Problem

We want a repeatable, locally-runnable way to compare Ollama-served LLMs across three capability dimensions:

- **Coding** — fix broken code so deterministic tests pass (Node.js, Python, .NET)
- **Reasoning** — read supplied documents and answer structured questions correctly
- **Agent tasks** — use tools to accomplish goals in a real environment (open URL, extract data, produce files)

Each dimension runs as a separate benchmark with its own task suite, scripts, model settings, and history file. Results are not mixed across types.

#### Users

- Developer choosing a "daily driver" or "heavy lifter" local model for coding.
- Researcher or analyst evaluating model document comprehension.
- Engineer assessing agentic capability for automated workflows.

#### Success Metrics (all types)

- Each benchmark runs end-to-end locally with one command.
- Results are reproducible (pinned tasks, deterministic settings).
- Clear pass/fail reporting with failure categorisation.
- Adding a new task takes <30 minutes.

---

### Benchmark Types

| Type | Version | Status | Entry point | Task data |
|---|---|---|---|---|
| Coding | v1 | Implemented | `compare.sh` | `task_data/` |
| Reasoning | v2 | Designed, not yet implemented | `compare-reasoning.sh` | `task_data_reasoning/` |
| Agent tasks | v3 | Early design only | `compare-agent.sh` | `task_data_agent/` |

---

## Type 1: Coding Benchmark

### Functional Requirements

1) CLI Runner (`bench.py`)
- Entrypoint: `python3 bench.py` (or `./run.sh` which manages the venv).
- Accepts multiple models and runs all tasks for each model.
- Configurable flags:
  - `--models` (required, one or more)
  - `--tasks` (optional subset; default: all built-in)
  - `--ollama-url` (default: `http://localhost:11434`)
  - `--num-ctx` (default: 8192)
  - `--temperature` (default: 0.0)
  - `--seed` (default: 1)
  - `--num-predict` (default: 400)
  - `--model-timeout` (default: 300, seconds)
  - `--think` (enable thinking/reasoning mode for supported models)
  - `--warmup` (send a tiny prompt to each model before the benchmark loop to force model load; eliminates cold-start timing penalty on the first task)
  - `--out` (default: `output/results.json`)
  - `--keep-workdirs` (debug: skip temp dir cleanup)
- Prints live progress (`[i/total] model task ... PASS/FAIL wall_s tok/s`).
- Prints a comparison table and failure detail on completion.

2) Shell scripts
- `run.sh`: creates/activates a venv, installs `requirements.txt`, forwards all args to `bench.py`.
- `compare.sh`: reads a model set from `models/<set-name>.txt`; sets `--num-predict 2400 --model-timeout 900`; forwards extra args. Default set: `models/default.txt`. Named sets: `./compare.sh extended`, `./compare.sh full`.
- `preflight.sh`: checks all dependencies before a run (GPU, Ollama, models from `models/default.txt`, Python, Node, .NET).
- `fetch.sh`: pulls models by set name (`default`, `extended`), set file path, or bare model name.

3) Task Suite (`tasks.py` + `task_data/`)
- Built-in tasks (19 total, difficulty L1–L5):

  **Coding tasks (13):**
  - `python_safe_div` (L1) — `calc.safe_div` must raise `ValueError` on zero divisor; `pytest`
  - `dotnet_sas` (L1) — Azure SAS expiry is 10 min in the past; fix to 60 min future; `xUnit`
  - `node_slugify` (L2) — ESM `src/slug.js`; fix punctuation stripping + hyphen collapsing; `node --test`
  - `python_lru_cache` (L2) — `LRUCache.get()` must promote accessed node to MRU position; `pytest`
  - `python_multifile_rename` (L2) — `price_cents` renamed to `price` in `product.py`; fix two dependent files; model must output two `BEGIN_FILE` blocks; `pytest`
  - `node_csv_parser` (L3) — ESM `src/csv.js`; naive comma-split must handle quoted fields with embedded commas and escaped quotes; `node --test`
  - `python_lfu_cache` (L3) — `LFUCache._promote()` must update `min_freq` when a frequency bucket empties; `pytest`
  - `python_minheap` (L3) — `MinHeap._sift_down()` checks left child only; add missing right-child comparison so smallest of current/left/right is always chosen; `pytest`
  - `node_memoize_bug` (L3) — `memoize()` key uses only `String(args[0])`; must use `JSON.stringify(args)` to avoid stale cache on multi-arg calls; `node --test`
  - `python_ledger_bug` (L4) — `Ledger.transfer()` credits the destination before checking the source balance; a failed transfer corrupts the destination; fix by reordering check → debit → credit → log; `pytest`
  - `python_expr_eval` (L4) — `Parser.expr()` loops on `*`/`/` and `Parser.term()` loops on `+`/`-`, inverting arithmetic precedence; fix by swapping the operator sets so `expr` handles `+`/`-` and `term` handles `*`/`/`; `pytest`
  - `python_dijkstra` (L5) — `dijkstra()` marks nodes visited when enqueued instead of dequeued; shorter paths discovered later are silently ignored; fix by moving `seen.add()` to the dequeue point; `pytest`
  - `python_hashmap` (L5) — `HashMap.delete()` clears slots directly instead of writing a tombstone; breaks linear-probe chains causing `get()` to miss keys inserted after a colliding deletion; `pytest`

  **Context & retrieval tasks (6):**
  - `context_8k` / `context_16k` / `context_32k` / `context_64k` (L1) — incident archive at 4 sizes (100/200/400/800 records); model finds a specific resolution code at 50% depth; primary metric is tok/s collapse as KV cache fills VRAM. `context_64k` may show `CTX_TRUNCATED` on models where Ollama silently caps `num_ctx` below 65536.
  - `multihop_forward` (L3) — 400-record archive (~30k tokens); engineer K. Vasquez appears in exactly two incidents; anchor (INCIDENT-2000) at ~20%, answer at ~75%; model must carry the engineer name from hop 1 to locate hop 2.
  - `multihop_reverse` (L3) — same mechanic, reversed: answer incident at ~20% (before the anchor at ~75%); harder for non-thinking models to reason about, but easier for thinking models that scan forward and flag all K. Vasquez occurrences. Known: gpt-oss:20b passes reverse but fails forward — its thinking loop expands indefinitely scanning forward through a 30k-token document, exhausting even 8192 reasoning tokens; gpt-oss:120b handles both correctly.
- Each task must:
  - fail baseline tests deterministically (verified before the model call)
  - specify an editable allow-list (one file by default; two for cross-module tasks)
  - provide context files included verbatim in the prompt
  - define a test command as an argv list with a timeout

4) Model Interaction
- POST `/api/chat` (non-streaming) with options: `temperature`, `seed`, `num_ctx`, `num_predict`.
- Defaults enforce determinism: `temperature=0`, `seed=1`.
- Records Ollama-provided metrics: `prompt_eval_count`, `eval_count`, durations (ns).
- Derives `tok_per_s` from `eval_count / (eval_duration / 1e9)`.
- Between models: calls `unload_model()` (POST `/api/generate` with `keep_alive=0`) then polls until VRAM drains to near-baseline before taking `before_load` snapshot.

5) GPU Telemetry (optional; requires `nvidia-ml-py`)
- Three GPU snapshots per model switch: `before_load` (after idle-wait), `after_load` (after warmup).
- One peak-poll result per task: `peak_during_gen` — highest `gpu_util` sample seen across 500ms polls during the `chat()` call.
- Two VRAM readings per task: `vram_before_mb` (before `chat()`) and `vram_after_mb` (after `chat()`); delta used to compute `kv_mb_per_1k_tokens`.
- All GPU fields are `null` if pynvml is unavailable; benchmark otherwise unaffected.

5) Edit Application
- Parse `BEGIN_FILE <path> … END_FILE` blocks from raw model output.
- Reject edits to any file not in the task's editable allow-list.
- Apply edits by overwriting files in the isolated temp workdir.

6) Scoring
- Verify baseline fails before calling the model.
- Re-run tests after applying edits; pass = tests exit 0.
- Failures are categorised:
  - `BASELINE_PASSED_INVALID_TASK` — task fixture is broken
  - `NO_BLOCKS` — model produced no parseable edits
  - `CTX_TRUNCATED` — prompt was silently truncated by Ollama (num_ctx capped below request due to VRAM); detected when `prompt_eval_count < len(prompt) // 4`
  - `EDITED_NONEDITABLE_FILE` — model violated the allow-list
  - `TESTS_STILL_FAIL` — edits applied but tests still fail
  - `TOOL_ERROR` — setup/test runner timeout or crash

7) Outputs
- `output/results.json` (or the path passed to `--out`): list of records (one per model × task).
- Console comparison table: rows = models, columns = tasks + summary; each cell shows `PASS/FAIL`, `tok/s`, `wall_s`; `Spd` column shows assumed speed rank (1 = fastest, by model set order).
- Console failure detail: error kind counts + one-line sample per category.
- `output/compare-history.json`: last 10 run summaries with per-model/per-task breakdown; used to show estimated runtime in the compare header.

### Result Record Schema

Per model × task run:

| Field | Type | Notes |
|---|---|---|
| `model` | string | |
| `task` | string | |
| `baseline_failed` | bool | expected true; false → `BASELINE_PASSED_INVALID_TASK` |
| `baseline_rc` | int | 0 or 1 |
| `edit_parse_ok` | bool | at least one `BEGIN_FILE` block found |
| `edit_policy_ok` | bool | no allow-list violations |
| `tests_pass` | bool | final test run exit code 0 |
| `edited_files` | list[string] | paths actually written |
| `error_kind` | string\|null | see categories above |
| `error_detail` | string\|null | truncated output snippet |
| `metrics` | object | `num_ctx`, `prompt_eval_count`, `eval_count`, `*_duration_ms` |
| `tok_per_s` | float | derived from Ollama eval metrics |
| `wall_s` | float | total elapsed seconds including setup + model call + tests |
| `response_truncated` | bool | true if `eval_count >= num_predict - 5` |
| `ctx_truncated` | bool | true if prompt was silently truncated (Ollama capped num_ctx below request) |
| `response_snippet` | string\|null | first/last 150 chars of raw model output for debugging |
| `gpu_snapshots` | object\|null | `before_load` (with `dirty` flag), `after_load`, `peak_during_gen`; null if pynvml unavailable |
| `kv_cache` | object\|null | `vram_before_mb`, `vram_after_mb`, `delta_mb`, `prompt_tokens`, `gen_tokens`, `total_tokens`, `kv_mb_per_1k_tokens`; null if pynvml unavailable or inference failed |

### Recommended Settings

| Setting | Value | Notes |
|---|---|---|
| `--num-ctx` | 8192 | Default; increase for large prompt tasks |
| `--num-predict` | 2400 | Thinking models use tokens for reasoning before BEGIN_FILE |
| `--model-timeout` | 1200 | 120B RAM-bound models can exceed 900s at large context (compare.sh default) |
| `--think` | off | Thinking tokens consume budget before the code block appears |
| `--temperature` | 0.0 | Reproducibility |

### Task Authoring Contract

1. Baseline tests **fail** (`test_cmd` exits non-zero on unmodified `task_data/`).
2. After the correct minimal fix to `editable_files`, tests **pass**.
3. `editable_files` allow-list is as small as possible (ideally one file).
4. `context_files` provide everything the model needs to understand the fix (tests, config).

### Example CLI

```bash
# All benchmark models, all tasks
./compare.sh

# Specific model or task subset
./run.sh --models qwen3-coder:30b --tasks python_safe_div node_csv_parser

# Larger context window
./compare.sh --num-ctx 16384

# Keep workdirs for debugging a failure
./run.sh --models qwen2.5-coder:14b --tasks node_csv_parser --keep-workdirs
```

---

## Type 2: Reasoning Benchmark

### Overview

Models are given one or more documents (plain text, extracted PDF, CSV, scraped news article) as context and must answer a set of structured questions. Answers are written to a single output file (`answer.txt`) using the same `BEGIN_FILE/END_FILE` protocol as coding tasks — requiring **zero harness code changes**.

**Status: designed, not yet implemented.**

### Functional Requirements

1) Scripts
- `compare-reasoning.sh`: equivalent of `compare.sh` for reasoning tasks; sources `bench-reasoning-models.sh`; sets `--num-ctx 32768 --num-predict 800 --model-timeout 900`.
- `bench-reasoning-models.sh`: canonical model list for reasoning runs (same models as coding initially).
- `compare-reasoning-history.json`: separate history file for reasoning runs.

2) Task Suite (`task_data_reasoning/`)

Each reasoning task:
- Has one editable file: `answer.txt` (empty or placeholder baseline — tests must fail).
- Has one or more context files in `documents/`: the documents to reason about.
- Defines a test command: `python -m pytest tests/ -v --tb=short`.
- The test script reads `answer.txt` and checks each answer against `expected.json`.

3) Answer Protocol

Model output must be a single `BEGIN_FILE answer.txt … END_FILE` block.

Answer file format (one line per question):
```
Q1: <answer>
Q2: <answer>
Q3: <answer>
```

4) Scoring

Each question in `expected.json` specifies a `match` type:

| Match type | Rule |
|---|---|
| `exact` | Case-insensitive string equality after stripping whitespace |
| `normalized` | Strip units, punctuation, and extra whitespace before comparing |
| `contains` | Expected string appears anywhere in the answer |
| `numeric` | Parse both as floats; pass if within ±1% (or absolute ±0.5 for small values) |

Overall task result: `tests_pass = True` only if **all** questions pass. Individual question results are recorded in `error_detail` for later partial-score analysis.

5) Additional Failure Categories (reasoning-specific)

- `WRONG_ANSWERS` — `answer.txt` produced and parseable but one or more answers are incorrect.
- `MALFORMED_ANSWERS` — `answer.txt` does not contain the expected Q-line format.

### Task File Layout

```
task_data_reasoning/
  <task_id>/
    documents/
      article.txt       # plain text — web scrape cleaned to article body only
      article.pdf       # original PDF for reference (text pre-extracted to .txt for prompts)
      data.csv          # supporting tabular data
      report.txt        # long spec or report; note if chunking is needed
    answer.txt          # editable baseline (empty or placeholder — tests must fail)
    expected.json       # ground truth answers
    tests/
      test_answers.py   # reads answer.txt, scores against expected.json
```

**expected.json schema:**
```json
[
  {
    "id":       "Q1",
    "question": "What date was the report published?",
    "expected": "2024-03-15",
    "match":    "exact"
  },
  {
    "id":       "Q2",
    "question": "What was the projected GDP figure mentioned in the article?",
    "expected": "47.3",
    "match":    "numeric"
  },
  {
    "id":       "Q3",
    "question": "Which country ranked first in the index?",
    "expected": "Netherlands",
    "match":    "exact"
  }
]
```

### Recommended Settings

| Setting | Value | Reason |
|---|---|---|
| `--num-ctx` | 32768–131072 | Documents can be large; match to longest document |
| `--num-predict` | 400–800 | Answers are short; leave budget for long-doc prefill |
| `--model-timeout` | 1200 | Long prefill for large context windows |
| `--think` | Test both on/off | Reasoning tokens may help or hurt; worth comparing |
| `--temperature` | 0.0 | Reproducibility |

### Task Authoring Contract

1. Baseline `answer.txt` must be empty or contain wrong answers — tests must fail before the model runs.
2. Questions must have genuinely unambiguous answers determinable solely from the supplied documents.
3. Prefer `exact` or `numeric` match types; use `contains` only when the answer is a proper noun or phrase that could not be accidentally present.
4. Note the document and approximate location of each answer in a comment in `expected.json`.
5. Verify the correct answers manually against the source document before committing.

### Document Types and Sourcing

| File type | Where to put it | Notes |
|---|---|---|
| Web article (scraped) | `documents/article.txt` | Strip nav, ads, and boilerplate; keep article body only |
| Original PDF | `documents/article.pdf` | Keep for reference; extract text to `.txt` for model prompts |
| CSV / data table | `documents/data.csv` | Include as-is — models handle CSV well in context |
| Long report or spec | `documents/report.txt` | Note if chunking is needed for very long docs (>100K tokens) |

---

## Type 3: Agent Benchmark

### Overview

Models are given a natural-language goal and access to tools (browser, shell, file system) and must accomplish it autonomously in a multi-turn conversation. This requires a new harness component (`bench_agent.py`) and is significantly more complex than Types 1 and 2.

**Status: early design only. Not yet implemented.**

### Key Differences from Types 1 and 2

| Aspect | Coding / Reasoning | Agent |
|---|---|---|
| Turns | Single turn | Multi-turn (model calls tools, observes results, continues) |
| Output protocol | `BEGIN_FILE/END_FILE` blocks | Tool-call JSON (Ollama function calling API) |
| Verification | Run tests / check answers | Inspect environment state after task completes |
| Model requirement | Any Ollama model | Must support Ollama function/tool calling |
| Harness | `bench.py` (existing) | `bench_agent.py` (new) |
| Reproducibility | High (deterministic) | Lower (depends on external state, network, timing) |

### Planned Task Types

- **Web extraction**: navigate to a URL, extract a specific data point, write it to a file.
- **File conversion**: read an input file, transform format (e.g. CSV → PDF), verify output.
- **Multi-step research**: retrieve information from multiple sources, produce a summary file.

### Task File Layout

```
task_data_agent/
  <task_id>/
    goal.txt            # natural language task description shown to the model
    tools.json          # which tools are available for this task (browser, shell, file)
    setup/              # seed files placed in workdir before the agent runs
    expected/           # expected output files or state patterns for verification
    tests/
      verify.py         # checks workdir state after agent run completes
```

### Planned Settings

| Setting | Value | Reason |
|---|---|---|
| `--num-ctx` | 32768+ | Multi-turn history accumulates rapidly |
| `--num-predict` | Unlimited per turn | Agent must reason and call tools freely |
| `--think` | On | Complex multi-step goals benefit from reasoning tokens |
| `--temperature` | 0.0 | Reproducibility |
| `--max-turns` | TBD (new flag) | Prevent runaway tool-calling loops |

### Out of Scope (v3 pre-implementation)

- Auto-sandboxing of browser or OS environment.
- Scoring of intermediate steps (only final state is verified).
- Partial credit for partially-completed goals.
- Models without Ollama function-calling support.

---

## Common: Non-functional Requirements

- Works on WSL Ubuntu (primary environment).
- Minimal dependencies: stdlib-only for harness core; `pytest` for task test scripts.
- Timeouts on all subprocess calls and model HTTP calls.
- Temp workdirs deleted after each run (unless `--keep-workdirs`).
- History and results files live in `output/` (git-ignored); the directory is created automatically on first run.

## Common: Out of Scope (current)

- Auto-downloading models (use `fetch.sh`).
- Web UI or HTML dashboard.
- JSONL output format.
- Container sandbox for untrusted task repos.
- Multi-turn repair loops for coding tasks.
- Cross-type combined result tables.

## Future Enhancements

- **Reasoning**: partial scoring with per-question breakdown in results JSON.
- **Reasoning**: paired `--think on/off` runs with automatic delta comparison.
- **Reasoning**: vision-capable model support for PDF screenshots (vs. pre-extracted text).
- **Agent**: `bench_agent.py` with Ollama function-calling loop and `--max-turns` flag.
- **Agent**: browser automation via Playwright for web extraction tasks.
- **All types**: multiple trials per model/task with confidence intervals.
- **All types**: HTML report generation.
- **All types**: external task definitions in YAML (repo path, test command, editable files, context globs).
