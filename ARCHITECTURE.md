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
ollama_client.py          POST /api/chat (non-streaming), metrics extraction; unload_model()
parsing.py                BEGIN_FILE/END_FILE parser, allow-list validation
reporting.py              Comparison table, failure detail, JSON writer
gpu_monitor.py            pynvml GPU telemetry: snapshots, peak poller, idle-wait with VRAM drain check
requirements.txt          pytest + nvidia-ml-py (optional; bench runs without it)
run.sh                    Venv setup + bench.py entrypoint
compare.sh                Runs canonical 6-model set; sources bench-models.sh; forwards extra args
compare-extended.sh       Runs all 8 evaluated models × all tasks; writes results-extended.json
bench-models.sh           Canonical model list (ordered fastest → slowest); sourced by compare/preflight/install
preflight.sh              Dependency checker (GPU, Ollama, models, Python, Node, .NET)
install-models.sh         Pulls any missing models from bench-models.sh
show-all-models.sh        Runs ollama show on every locally installed model
compare-history.json      Run summaries + per-model history archive (git-ignored, machine-local)
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
  python_minheap/         minheap.py (baseline), tests/test_minheap.py
  python_multifile_rename/ product.py (context), inventory.py + reports.py (baseline, 2 editable files), tests/
  node_memoize_bug/       package.json, src/memoize.js (baseline), src/pricing.js (context), tests/pricing.test.js
  python_ledger_bug/      ledger.py (baseline), account.py (context), tests/test_ledger.py
  python_expr_eval/       expr_eval.py (baseline), tests/test_expr_eval.py
  python_dijkstra/        dijkstra.py (baseline), tests/test_dijkstra.py
  python_hashmap/         hashmap.py (baseline), tests/test_hashmap.py

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
- At startup: captures `system_baseline_vram_mb` from `get_gpu_snapshot()` (before any model loads) for use as the VRAM drain reference between models.
- On model switch: calls `unload_model(previous_model)` to explicitly evict weights from VRAM, then calls `wait_for_gpu_idle(baseline_vram_mb=…)` which polls until `gpu_util < 5%` AND `vram_used_mb < baseline + 200 MB` AND VRAM stable between polls (10s timeout; marks snapshot `dirty: true` on timeout and prints a warning).
- If `--warmup`: sends a tiny prompt to each model just before its first task (JIT, not bulk upfront) using `keep_alive=-1` to keep it resident through all its tasks. Captures `gpu_after` snapshot post-warmup.
- Per task in `run_one()`: takes `vram_pre` snapshot before `chat()`, starts `launch_peak_poller()` thread, calls `chat()`, takes `vram_post` immediately after, stops the poller, stores `peak_during_gen`.
- Calls `run_one()` per pair; collects result records.
- On completion: writes `results.json`, prints comparison table, prints failure detail.

#### `tasks.py` — Task Library + Prompt Builder

Two responsibilities kept in one module to avoid a thin `prompting.py` abstraction:

- **`Task` dataclass**: `id`, `description`, `subdir`, `editable_files`, `context_files`, `test_cmd`, `test_timeout`, `setup_cmd`, `setup_timeout`, `difficulty` (1=L1/2=L2/3=L3/4=L4/5=L5, used for the Skill column), `num_ctx` (optional per-task context window override — runner uses `max(global, task.num_ctx)`), `min_predict` (optional per-task floor on `--num-predict`; useful when thinking models need extended token budget for reasoning before output).
- **`build_prompt(task, workdir)`**: reads file contents and assembles the user message with `BEGIN_FILE/END_FILE` blocks for editable files and `--- path ---` fenced sections for context files.
- **`prepare_workdir`**, **`run_setup`**, **`run_tests`**: thin subprocess wrappers using `subprocess.run(..., timeout=...)`.
- **`BUILTIN_TASKS` / `TASK_MAP`**: the built-in task list and a lookup dict by task id.

#### `ollama_client.py` — Model Adapter

- `chat(...)` — main inference call. Uses `urllib.request` (stdlib); no third-party HTTP library. Accepts `think: bool` (reasoning tokens), `num_thread: int | None` (CPU cap), `keep_alive: str | int | None` (warmup calls use `-1` to keep model resident). Returns `OllamaResponse(content, thinking, metrics)`.
- `unload_model(base_url, model, timeout)` — POSTs to `/api/generate` with `keep_alive=0` to immediately evict model weights from VRAM. Fire-and-forget; exceptions swallowed. Called by `bench.py` before each model switch so the VRAM drain wait has something to wait for.

#### `gpu_monitor.py` — GPU Telemetry

Optional module; requires `nvidia-ml-py` (`pip install nvidia-ml-py`). Fails gracefully with a `RuntimeWarning` if pynvml is unavailable — all functions return `None` and the benchmark continues normally.

- `get_gpu_snapshot() -> dict | None` — single point-in-time sample: `vram_used_mb`, `gpu_util`, `mem_bandwidth_util` for GPU 0.
- `wait_for_gpu_idle(timeout, baseline_vram_mb, …) -> dict | None` — polls every 500ms until all three conditions hold simultaneously: `gpu_util < 5%`, `vram_used_mb < baseline_vram_mb + 200`, and VRAM delta < 50 MB between consecutive polls. Hard timeout: 10s. On timeout: returns last snapshot with `"dirty": True`; clean exit returns snapshot with `"dirty": False`. Used between model loads to ensure `before_load` captures true idle baseline.
- `launch_peak_poller(stop_event, poll_interval) -> (Thread, list)` — background thread that polls every 500ms until `stop_event` is set, then does one final poll. Records the sample with the highest `gpu_util` seen across all polls. Captures genuine peak GPU activity regardless of task duration (replaces the old fixed 5-second delayed snapshot which missed short tasks).

#### `parsing.py` — Edit Protocol Parser

- `parse_file_blocks(text)` — regex over `BEGIN_FILE <path>\n…\nEND_FILE`; returns `list[FileEdit]`.
- `validate_edits(edits, allow_list)` — returns violation strings for any path outside the allow-list.

#### `reporting.py` — Output

- `print_comparison_table(results, task_difficulties)` — ASCII table: rows = models, columns = `Spd` (assumed speed rank) + `Skill` (highest difficulty tier where model passes all tasks) + tasks + summary. Each task cell shows `PASS/FAIL`, `tok/s`, `wall_s`; the sub-header shows the task's difficulty level `(L1)/(L2)/(L3)/(L4)`. The Skill column and legend are derived dynamically from the current task set's max difficulty.
- `print_summary(results)` — failure detail: error kind counts + one-line sample per category.
- `write_results(results, path)` — JSON dump.

#### `compare-history.json` — Run + Model Archive

Written by `compare.sh` after each run. Two top-level sections:

- **`runs`** — last 10 full run summaries (timestamp, models, tasks, overall pass/fail, per-model breakdown). Used by the `compare.sh` header to show estimated runtime for the next run.
- **`model_history`** — dict keyed by model name; each value is a list of that model's last 10 run entries (`timestamp`, `passes`, `total_tasks`, `avg_tok_per_s`, `total_wall_s`, `per_task`). Persists across model set changes — models swapped out of `bench-models.sh` retain their history and appear in the header as "Archived models".

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
| `metrics` | object | `num_ctx`, `prompt_eval_count`, `eval_count`, `prompt_eval_duration_ms`, `eval_duration_ms`, `total_duration_ms` |
| `tok_per_s` | float | |
| `wall_s` | float | total including setup + model + tests |
| `response_truncated` | bool | true if `eval_count >= num_predict - 5` |
| `response_snippet` | string\|null | first/last 150 chars of raw model output for debugging |
| `gpu_snapshots` | object\|null | see below; null if pynvml unavailable |
| `kv_cache` | object\|null | see below; null if pynvml unavailable or inference failed |

**`gpu_snapshots` fields:**

| Field | Notes |
|---|---|
| `before_load` | Snapshot after previous model evicted + VRAM drained to idle. Includes `dirty: true` if the 10s wait timed out with VRAM still above baseline. |
| `after_load` | Snapshot after warmup completes (weights resident). `null` if `--warmup` not used. |
| `peak_during_gen` | Sample with highest `gpu_util` seen across 500ms polls during the `chat()` call. Captures peak GPU activity regardless of task duration. |

Each snapshot: `{vram_used_mb, gpu_util, mem_bandwidth_util}` plus `dirty` (bool) on `before_load`.

**`kv_cache` fields:**

| Field | Notes |
|---|---|
| `vram_before_mb` | VRAM immediately before `chat()` — weights loaded, no KV cache for this request |
| `vram_after_mb` | VRAM immediately after `chat()` returns — weights + full KV cache |
| `delta_mb` | `max(0, vram_after_mb - vram_before_mb)` — KV cache allocation (prompt + output tokens) |
| `prompt_tokens` | `prompt_eval_count` from Ollama metrics |
| `gen_tokens` | `eval_count` from Ollama metrics |
| `total_tokens` | `prompt_tokens + gen_tokens` |
| `kv_mb_per_1k_tokens` | `delta_mb / total_tokens * 1000`; null if delta is 0 |

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
- Thinking models (gpt-oss:20b, gpt-oss:120b, qwen3.5:35b) consume generation tokens for reasoning before emitting `BEGIN_FILE`; `--num-predict 2400` is the minimum for complex tasks (`compare.sh` sets this explicitly). Per-task `min_predict` overrides handle tasks where reasoning alone can exceed the default budget — e.g. `python_lfu_cache` and `python_minheap` use `min_predict=12800` because gpt-oss:20b burns ~5500 tokens of thinking before outputting the fix.
- Warmup is JIT per model: each model is warmed up immediately before its first task, not all at the start. Calls use `keep_alive=-1` so the model stays resident through all its tasks; memory-pressure eviction still applies.
- `--num-thread 10` caps CPU threads per inference request; negligible effect on GPU-bound models but reduces heat on the host CPU.
- GPU monitoring requires `nvidia-ml-py` and an NVIDIA GPU. Without it, `gpu_snapshots` and `kv_cache` fields are `null`; the benchmark otherwise runs identically.
- Ollama keeps the previous model's weights in VRAM after the last request (even when GPU utilisation drops to 0%). `unload_model()` + `wait_for_gpu_idle()` forces a clean drain before each model switch, but if Ollama doesn't evict within 10s the snapshot is marked `dirty: true`.
- KV cache delta (`kv_cache.delta_mb`) covers both prompt and output tokens since the full KV cache is allocated across the complete inference call. Prompt tokens dominate for typical task prompt sizes (400–700 tokens vs. 50–200 generated).

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
