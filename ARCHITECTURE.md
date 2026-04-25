### Overview

This repo contains a local, reproducible benchmark harness for evaluating coding-capable LLMs served by **Ollama** (running locally, typically in WSL). The harness runs a suite of deterministic tasks (Node.js, Python, .NET/Azure-flavored) against one or more models and scores them on:

- **Correctness:** do tests pass after applying the model's edits?
- **Edit validity:** did the model produce machine-parseable edits?
- **Safety/discipline:** did it modify only allowed files?
- **Performance:** wall-clock time, tokens/sec, prompt/eval token counts

Key design choice: use a **whole-file edit protocol** instead of diffs (more robust for local models).

### Repository Layout

```
bench.py            CLI runner — orchestrates model × task matrix
tasks.py            Task dataclass, built-in task definitions, prompt builder, subprocess helpers
ollama_client.py    POST /api/chat (non-streaming), metrics extraction
parsing.py          BEGIN_FILE/END_FILE parser, allow-list validation
reporting.py        Comparison table, failure detail, JSON writer
requirements.txt    pytest only (harness is stdlib-first)
run.sh              Venv setup + bench.py entrypoint
compare.sh          Runs canonical 4-model set; forwards extra args to run.sh
preflight.sh        Dependency checker (GPU, Ollama, models, Python, Node, .NET)
tests/
  conftest.py         sys.path shim
  test_parsing.py     Unit tests for the BEGIN_FILE/END_FILE parser
task_data/
  node_slugify/     package.json, src/slug.js (baseline), tests/slug.test.js
  python_safe_div/  calc.py (baseline), conftest.py, tests/test_calc.py
  dotnet_sas/       MicroAzureSas.sln, src/…/SasHelper.cs (baseline), tests/…/SasHelperTests.cs
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

- **`Task` dataclass**: `id`, `description`, `subdir`, `editable_files`, `context_files`, `test_cmd`, `test_timeout`, `setup_cmd`, `setup_timeout`.
- **`build_prompt(task, workdir)`**: reads file contents and assembles the user message with `BEGIN_FILE/END_FILE` blocks for editable files and `--- path ---` fenced sections for context files.
- **`prepare_workdir`**, **`run_setup`**, **`run_tests`**: thin subprocess wrappers using `subprocess.run(..., timeout=...)`.
- **`BUILTIN_TASKS` / `TASK_MAP`**: the three built-in tasks and a lookup dict.

#### `ollama_client.py` — Model Adapter

- Single public function `chat(...)`.
- Uses `urllib.request` (stdlib); no third-party HTTP library.
- Accepts `think: bool` to enable reasoning tokens for models that support it (deepseek-r1, gemma4, etc.).
- Returns `OllamaResponse(content, thinking, metrics)` where `thinking` holds the model's reasoning trace and `metrics.tok_per_s` is derived from `eval_count / (eval_duration_ns / 1e9)`.

#### `parsing.py` — Edit Protocol Parser

- `parse_file_blocks(text)` — regex over `BEGIN_FILE <path>\n…\nEND_FILE`; returns `list[FileEdit]`.
- `validate_edits(edits, allow_list)` — returns violation strings for any path outside the allow-list.

#### `reporting.py` — Output

- `print_comparison_table(results)` — ASCII table: rows = models, columns = tasks + summary. Each cell shows `PASS/FAIL`, `tok/s`, `wall_s`. Summary column shows pass count, avg tok/s, total seconds.
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
3. `editable_files` allow-list is as small as possible (ideally one file).
4. `context_files` provide everything the model needs to understand the fix (tests, config).

### Security / Safety Notes

- Tasks run arbitrary code (tests). Only run trusted task suites.
- Each run gets an isolated `tempfile.mkdtemp()` directory; the source `task_data/` is never modified.
- `subprocess.run` is used throughout; `shell=True` is never used.

### Extensibility

**Adding a task:**

```python
MY_TASK = Task(
    id="my_task",
    description="Fix the bug in src/foo.py so tests pass.",
    subdir="my_task",           # → task_data/my_task/
    editable_files=["src/foo.py"],
    context_files=["tests/test_foo.py"],
    test_cmd=["python", "-m", "pytest", "tests/"],
    test_timeout=30,
)
```

Then add `task_data/my_task/` with baseline source + tests, and register `MY_TASK` in `BUILTIN_TASKS`.

**Future: external repo mode** — define tasks in YAML pointing at local repo paths with a test command and editable allow-list.

### Known Constraints

- First run of `npm install` / `dotnet restore` fetches packages from the internet; subsequent runs use the local cache.
- Models that violate the output format produce `NO_BLOCKS`; the harness does not attempt a repair pass.
- Large context windows increase KV cache pressure; speed varies by model quantization and VRAM.
