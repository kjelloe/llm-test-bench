### Overview

This repo contains a local, reproducible benchmark harness for evaluating LLMs served by **Ollama** (running locally, typically in WSL) across three capability dimensions:

- **Coding (v1 — implemented):** fix broken code so deterministic tests pass.
- **Reasoning (v2 — designed):** read documents and answer structured questions.
- **Agent tasks (v3 — early design):** use tools to accomplish goals in a real environment.

Each type runs as a separate benchmark. This document covers the implemented architecture (v1) and the planned architecture (v2, v3).

For the coding benchmark specifically, the harness scores models on:

- **Correctness:** do tests pass after applying the model's edits?
- **Edit validity:** did the model produce machine-parseable edits?
- **Safety/discipline:** did it modify only allowed files?
- **Performance:** wall-clock time, tokens/sec, prompt/eval token counts

Key design choice: use a **whole-file edit protocol** instead of diffs (more robust for local models).

### Repository Layout

```
# ── Coding benchmark (v1 — implemented) ─────────────────────────────────────
bench.py                  CLI runner — orchestrates model × task matrix
tasks.py                  Task dataclass, built-in task definitions, prompt builder, subprocess helpers
ollama_client.py          POST /api/chat (non-streaming), metrics extraction
parsing.py                BEGIN_FILE/END_FILE parser, allow-list validation
reporting.py              Comparison table, failure detail, JSON writer
requirements.txt          pytest only (harness is stdlib-first)
run.sh                    Venv setup + bench.py entrypoint
compare.sh                Runs canonical model set; sources bench-models.sh; forwards extra args
bench-models.sh           Canonical model list (ordered fastest → slowest); sourced by compare/preflight/install
preflight.sh              Dependency checker (GPU, Ollama, models, Python, Node, .NET)
install-models.sh         Pulls any missing models from bench-models.sh
show-all-models.sh        Runs ollama show on every locally installed model
compare-history.json      Last 10 coding run summaries (git-ignored, machine-local)
tests/
  conftest.py             sys.path shim
  test_parsing.py         Unit tests for the BEGIN_FILE/END_FILE parser
task_data/
  node_slugify/           package.json, src/slug.js (baseline), tests/slug.test.js
  python_safe_div/        calc.py (baseline), conftest.py, tests/test_calc.py
  dotnet_sas/             MicroAzureSas.sln, src/…/SasHelper.cs (baseline), tests/…/SasHelperTests.cs
  node_csv_parser/        package.json, src/csv.js (baseline), tests/csv.test.js
  python_lru_cache/       lru_cache.py (baseline), conftest.py, tests/test_lru_cache.py
  python_lfu_cache/       lfu_cache.py (baseline), tests/test_lfu_cache.py
  python_bst_delete/      bst.py (baseline), tests/test_bst.py
  python_multifile_rename/ product.py (context), inventory.py + reports.py (baseline, 2 editable files), tests/

# ── Reasoning benchmark (v2 — planned) ──────────────────────────────────────
compare-reasoning.sh      (planned) Reasoning equivalent of compare.sh
bench-reasoning-models.sh (planned) Model list for reasoning runs
compare-reasoning-history.json  (planned, git-ignored)
task_data_reasoning/
  <task_id>/
    documents/            Source documents (article.txt, data.csv, report.txt, article.pdf)
    answer.txt            Editable baseline (empty — model fills this)
    expected.json         Ground truth: [{id, question, expected, match}]
    tests/
      test_answers.py     Reads answer.txt, scores against expected.json

# ── Agent benchmark (v3 — early design) ─────────────────────────────────────
bench_agent.py            (planned) Multi-turn tool-calling harness
compare-agent.sh          (planned) Agent equivalent of compare.sh
task_data_agent/
  <task_id>/
    goal.txt              Natural language task description
    tools.json            Available tools for this task
    setup/                Seed files placed in workdir before agent runs
    expected/             Expected output files / state for verification
    tests/
      verify.py           Checks workdir state after agent run completes
```

### Goals

- Run locally, offline except for initial package restores (npm, pip, nuget).
- Reproducible runs: deterministic settings (`seed=1`, `temperature=0`), pinned task fixtures.
- Model-agnostic via Ollama `/api/chat`.
- Easy to extend: adding a task means adding a `Task(…)` definition and a `task_data/` subfolder.
- Produce artifacts suitable for CI and dashboards: JSON output + console table.

### Non-goals

- Not a comprehensive "human eval" system.
- Not intended to benchmark multimodal features.
- Not a general agent; it is a benchmark harness with strict IO protocols.

### High-level Flow

For each `(model, task)` pair:

1. **Copy** `task_data/<task.subdir>/` into a fresh `tempfile.mkdtemp()` workdir.
2. **Setup** — run `task.setup_cmd` if present (e.g. `npm install`, `dotnet restore`).
3. **Baseline verification** — run `task.test_cmd`; assert it exits non-zero. If it passes, record `BASELINE_PASSED_INVALID_TASK` and skip.
4. **Prompt** — read editable + context files from workdir; build a structured prompt with the `BEGIN_FILE/END_FILE` format rules (see `tasks.build_prompt`).
5. **Model call** — POST `/api/chat` via `ollama_client.chat()` with `stream=false` and deterministic options.
6. **Parse** — extract `BEGIN_FILE … END_FILE` blocks from raw response text (`parsing.parse_file_blocks`).
7. **Validate** — check all edited paths are in `task.editable_files` (`parsing.validate_edits`).
8. **Apply** — overwrite files in the workdir.
9. **Test** — re-run `task.test_cmd`; record `tests_pass`.
10. **Cleanup** — delete workdir (unless `--keep-workdirs`).

### System Components

#### `bench.py` — CLI Runner

- Parses CLI args; builds the `(model, task)` matrix.
- Calls `run_one()` per pair; collects result records.
- On completion: writes `results.json`, prints comparison table, prints failure detail.

#### `tasks.py` — Task Library + Prompt Builder

Two responsibilities kept in one module to avoid a thin `prompting.py` abstraction:

- **`Task` dataclass**: `id`, `description`, `subdir`, `editable_files`, `context_files`, `test_cmd`, `test_timeout`, `setup_cmd`, `setup_timeout`, `difficulty` (1=Easy/2=Medium/3=Hard, used for the Skill column), `num_ctx` (optional per-task context window override — runner uses `max(global, task.num_ctx)`).
- **`build_prompt(task, workdir)`**: reads file contents and assembles the user message with `BEGIN_FILE/END_FILE` blocks for editable files and `--- path ---` fenced sections for context files.
- **`prepare_workdir`**, **`run_setup`**, **`run_tests`**: thin subprocess wrappers using `subprocess.run(..., timeout=...)`.
- **`BUILTIN_TASKS` / `TASK_MAP`**: the built-in task list and a lookup dict by task id.

#### `ollama_client.py` — Model Adapter

- Single public function `chat(...)`.
- Uses `urllib.request` (stdlib); no third-party HTTP library.
- Accepts `think: bool` to enable reasoning tokens for models that support it (deepseek-r1, gemma4, etc.).
- Accepts `num_thread: int | None` to cap CPU threads (default 10 via CLI, passed per request).
- Accepts `keep_alive: str | int | None` — JIT warmup calls use `-1` (keep loaded until memory pressure evicts) so each model stays resident through all of its own tasks.
- Returns `OllamaResponse(content, thinking, metrics)` where `thinking` holds the model's reasoning trace and `metrics.tok_per_s` is derived from `eval_count / (eval_duration_ns / 1e9)`.

#### `parsing.py` — Edit Protocol Parser

- `parse_file_blocks(text)` — regex over `BEGIN_FILE <path>\n…\nEND_FILE`; returns `list[FileEdit]`.
- `validate_edits(edits, allow_list)` — returns violation strings for any path outside the allow-list.

#### `reporting.py` — Output

- `print_comparison_table(results, task_difficulties)` — ASCII table: rows = models, columns = `Spd` (assumed speed rank) + `Skill` (highest difficulty tier where model passes all tasks) + tasks + summary. Each task cell shows `PASS/FAIL`, `tok/s`, `wall_s`; the sub-header shows the task's difficulty level `(L1)/(L2)/(L3)`.
- `print_summary(results)` — failure detail: error kind counts + one-line sample per category.
- `write_results(results, path)` — JSON dump.

### Data Model (Result Record)

| Field | Type | Notes |
|---|---|---|
| `model` | string | |
| `task` | string | |
| `baseline_failed` | bool | |
| `baseline_rc` | int | |
| `edit_parse_ok` | bool | |
| `edit_policy_ok` | bool | |
| `tests_pass` | bool | |
| `edited_files` | list[string] | |
| `error_kind` | string\|null | `NO_BLOCKS`, `EDITED_NONEDITABLE_FILE`, `TESTS_STILL_FAIL`, `BASELINE_PASSED_INVALID_TASK`, `TOOL_ERROR` |
| `error_detail` | string\|null | truncated, max ~500 chars |
| `metrics` | object | `prompt_eval_count`, `eval_count`, `*_duration_ms` |
| `tok_per_s` | float | |
| `wall_s` | float | total including setup + model + tests |
| `response_truncated` | bool | true if `eval_count >= num_predict - 5` |
| `response_snippet` | string\|null | first/last 150 chars of raw model output for debugging |

### Edit Protocol (Whole-file)

Model output must consist solely of one or more blocks:

```
BEGIN_FILE <relative/path>
<full updated file content>
END_FILE
```

Strictness enforced:
- `NO_BLOCKS` if `parse_file_blocks` returns empty.
- `EDITED_NONEDITABLE_FILE` if any path is outside the task's `editable_files`.

### Task Authoring Contract

A valid task must satisfy:
1. Baseline tests **fail** (`test_cmd` exits non-zero on unmodified `task_data/`).
2. After the correct minimal fix to `editable_files`, tests **pass**.
3. `editable_files` allow-list is as small as possible (one file for single-bug tasks; two files for cross-module refactoring tasks).
4. `context_files` provide everything the model needs to understand the fix (tests, config, related modules).

### Security / Safety Notes

- Tasks run arbitrary code (tests). Only run trusted task suites.
- Each run gets an isolated `tempfile.mkdtemp()` directory; the source `task_data/` is never modified.
- `subprocess.run` is used throughout; `shell=True` is never used.

### Extensibility

**Adding a task:**

Single-file task:
```python
MY_TASK = Task(
    id="my_task",
    description="Fix the bug in src/foo.py so tests pass.",
    subdir="my_task",           # → task_data/my_task/
    editable_files=["src/foo.py"],
    context_files=["tests/test_foo.py"],
    test_cmd=["python3", "-m", "pytest", "tests/"],
    test_timeout=30,
    difficulty=2,
)
```

Multi-file task with a larger context window:
```python
MY_MULTIFILE_TASK = Task(
    id="my_multifile_task",
    description="A rename propagated in module_a.py but not in module_b.py or module_c.py. Fix both.",
    subdir="my_multifile_task",
    editable_files=["module_b.py", "module_c.py"],   # model must output two BEGIN_FILE blocks
    context_files=["module_a.py", "tests/test_all.py"],
    test_cmd=["python3", "-m", "pytest", "tests/"],
    test_timeout=30,
    difficulty=2,
    num_ctx=16384,              # runner uses max(global --num-ctx, this value)
)
```

Then add `task_data/my_task/` with baseline source + tests, and register the task in `BUILTIN_TASKS`.

**Future: external repo mode** — define tasks in YAML pointing at local repo paths with a test command and editable allow-list.

### Known Constraints

- First run of `npm install` / `dotnet restore` fetches packages from the internet; subsequent runs use the local cache.
- Models that violate the output format produce `NO_BLOCKS`; the harness does not attempt a repair pass.
- Large context windows increase KV cache pressure; speed varies by model quantization and VRAM. Per-task `num_ctx` overrides let individual tasks request more headroom without raising the global default.
- Thinking models (gpt-oss, qwen3.5) consume generation tokens for reasoning before emitting `BEGIN_FILE`; `--num-predict 2400` is the current minimum for complex tasks.
- Warmup is JIT per model: each model is warmed up immediately before its first task, not all at the start. Calls use `keep_alive=-1` so the model stays resident through all its tasks; memory-pressure eviction still applies.
- `--num-thread 10` caps CPU threads per inference request; negligible effect on GPU-bound models but reduces heat on the host CPU.

---

## Planned: Reasoning Benchmark (v2)

### Design Approach

Reuse `bench.py` and the `BEGIN_FILE/END_FILE` protocol without modification. The "editable file" is `answer.txt`; the "tests" are a small pytest script that checks answers against `expected.json`. All existing harness features (workdir isolation, timeout handling, metrics, comparison table) apply unchanged.

### High-level Flow

For each `(model, task)` pair:

1. **Copy** `task_data_reasoning/<task.subdir>/` into a fresh workdir.
2. **Baseline verification** — run `pytest tests/`; assert it exits non-zero (empty `answer.txt` fails).
3. **Prompt** — context files are the documents in `documents/`; editable file is `answer.txt`.
4. **Model call** — same `ollama_client.chat()` with larger `--num-ctx` (32768+).
5. **Parse** — extract `BEGIN_FILE answer.txt … END_FILE` from response.
6. **Apply** — write model's `answer.txt` to workdir.
7. **Test** — run `pytest tests/`; `test_answers.py` reads `answer.txt`, compares each Q-line against `expected.json` using the configured match type (`exact`, `normalized`, `numeric`, `contains`).
8. **Cleanup** — delete workdir.

### New Components Required

| Component | What it does |
|---|---|
| `compare-reasoning.sh` | Sources `bench-reasoning-models.sh`; sets `--num-ctx 32768 --num-predict 800`; writes `results-reasoning.json`; updates `compare-reasoning-history.json` |
| `bench-reasoning-models.sh` | Same structure as `bench-models.sh`; may include same models but with different settings |
| `test_answers.py` (per task) | Reads `answer.txt`; parses Q-lines; compares against `expected.json`; fails if any answer is wrong |

### Answer Match Types

```python
# exact:      answer.strip().lower() == expected.strip().lower()
# normalized: strip punctuation/units/extra spaces, then exact
# numeric:    abs(float(answer) - float(expected)) / max(float(expected), 1) <= 0.01
# contains:   expected.strip().lower() in answer.strip().lower()
```

### Settings Differences vs. Coding

| Setting | Coding | Reasoning |
|---|---|---|
| `--num-ctx` | 8192 | 32768–131072 |
| `--num-predict` | 2400 | 400–800 (answers are short) |
| `--think` | Off | Test both on/off |

---

## Planned: Agent Benchmark (v3)

**Status: early design only. No implementation started.**

### Why a New Harness

Agent tasks require a multi-turn conversation loop: the model calls a tool, the harness executes it, the result is appended to the conversation, and the model continues. This cannot be expressed as a single `chat()` call. `bench_agent.py` will implement this loop with a configurable `--max-turns` limit.

### Planned High-level Flow

1. **Setup** — copy `task_data_agent/<task.subdir>/setup/` into workdir; make tools available.
2. **Turn loop** — call `ollama_client.chat()` with accumulated conversation history.
   - If response contains a tool call: execute the tool, append result to history, continue.
   - If response contains no tool call: treat as task completion.
   - If `--max-turns` reached: record `TOOL_ERROR`.
3. **Verify** — run `tests/verify.py`; inspect workdir state; record `tests_pass`.
4. **Cleanup** — delete workdir.

### Tool Interface (planned)

Tools are defined in `tools.json` per task and made available to Ollama via the function-calling API:

```json
[
  {"name": "browser_get",   "description": "Fetch the text content of a URL"},
  {"name": "shell_run",     "description": "Run a shell command and return stdout"},
  {"name": "file_write",    "description": "Write content to a file in the workdir"},
  {"name": "pdf_convert",   "description": "Convert a file to PDF using LibreOffice"}
]
```

### Model Requirement

Only Ollama models with function-calling support can run agent tasks. Models without it will produce `NO_BLOCKS` on the first turn and be scored as a failure. `bench_agent.py` will warn at startup if a model is known to lack tool support.
