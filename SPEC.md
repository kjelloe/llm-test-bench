### Product Spec: Local LLM Coding Benchmark Harness (Ollama)

#### Problem

We want a repeatable way to compare local LLMs for coding tasks across:
- Node.js (primary)
- Python (secondary)
- .NET/Azure (business)

The benchmark should reflect real developer workflows (Aider "whole file" edits) and avoid fragile diff parsing. It must run locally with Ollama and produce clear pass/fail plus performance metrics.

#### Users

- Developer benchmarking local models before choosing "daily driver" vs "heavy lifter".
- Teams comparing a fixed set of local models on standardized tasks.

#### Success Metrics

- Benchmark runs end-to-end locally with one command.
- Results are reproducible across runs (given pinned tasks + deterministic model options).
- Clear report of why failures happened (format vs policy vs correctness).
- Adding a new task takes <30 minutes.

#### Functional Requirements

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
  - `--out` (default: `results.json`)
  - `--keep-workdirs` (debug: skip temp dir cleanup)
- Prints live progress (`[i/total] model task ... PASS/FAIL wall_s tok/s`).
- Prints a comparison table and failure detail on completion.

2) Shell scripts
- `run.sh`: creates/activates a venv, installs `requirements.txt`, forwards all args to `bench.py`.
- `compare.sh`: calls `run.sh` with the canonical set of benchmark models; forwards extra args.
- `preflight.sh`: checks all dependencies before a run (GPU, Ollama, models, Python, Node, .NET).

3) Task Suite (`tasks.py` + `task_data/`)
- Built-in tasks:
  - `node_slugify` — ESM `src/slug.js`; fix punctuation + whitespace collapsing; `node --test`
  - `python_safe_div` — `calc.safe_div` must raise `ValueError` on zero divisor; `pytest`
  - `dotnet_sas` — Azure SAS expiry in the past; fix to ~60 min future; `xUnit`
- Each task must:
  - fail baseline tests deterministically (verified before the model call)
  - specify an editable allow-list (one file by default)
  - provide context files included verbatim in the prompt
  - define a test command as an argv list with a timeout

4) Model Interaction
- POST `/api/chat` (non-streaming) with options: `temperature`, `seed`, `num_ctx`, `num_predict`.
- Defaults enforce determinism: `temperature=0`, `seed=1`.
- Records Ollama-provided metrics: `prompt_eval_count`, `eval_count`, durations (ns).
- Derives `tok_per_s` from `eval_count / (eval_duration / 1e9)`.

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
  - `EDITED_NONEDITABLE_FILE` — model violated the allow-list
  - `TESTS_STILL_FAIL` — edits applied but tests still fail
  - `TOOL_ERROR` — setup/test runner timeout or crash

7) Outputs
- `results.json`: list of records (one per model × task).
- Console comparison table: per-task `PASS/FAIL`, `tok/s`, `wall_s` per model; summary column with pass count, avg tok/s, total wall seconds.
- Console failure detail: error kind breakdown with a one-line sample per category.

#### Result Record Schema

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
| `metrics` | object | from Ollama response |
| `tok_per_s` | float | derived |
| `wall_s` | float | total elapsed seconds including setup + model call + tests |

#### Non-functional Requirements

- Works on WSL Ubuntu (primary environment).
- Minimal dependencies: stdlib-only for the harness; `pytest` for running the harness's own tests.
- Timeouts on all subprocess calls and model HTTP calls.
- Temp workdirs are deleted after each run (unless `--keep-workdirs`).

#### Example CLI

```bash
# All four benchmark models, all tasks
./compare.sh

# Specific models or tasks
./run.sh --models qwen2.5-coder:32b-instruct-q8_0 --tasks python_safe_div

# Larger context window, forwarded via compare.sh
./compare.sh --num-ctx 16384
```

#### Out of Scope (v1)

- Auto-downloading models.
- Web UI dashboard.
- Multi-turn repair loops.
- `bench.yaml` config file (use CLI flags).
- JSONL output format.
- Container sandbox for untrusted repos.

#### Future Enhancements

- External repo scenarios described in YAML (repo path, test command, editable files, context globs).
- Multiple trials per model/task with confidence intervals.
- HTML report generation.
- `--format table` pretty-print via `tabulate`.
