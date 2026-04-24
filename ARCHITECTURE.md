### Overview

This repo contains a local, reproducible benchmark harness for evaluating coding-capable LLMs served by **Ollama** (running locally, typically in WSL). The harness runs a suite of deterministic tasks (Node.js, Python, .NET/Azure-flavored) against one or more models and scores them on:

- **Correctness:** do tests pass after applying the model’s edits?
- **Edit validity:** did the model produce machine-parseable edits?
- **Safety/discipline:** did it modify only allowed files?
- **Performance:** wall-clock time, tokens/sec (from Ollama metrics), prompt/eval token counts

Key design choice: use a **whole-file edit protocol** instead of diffs (more robust for local models).

### Goals

- Run locally, offline except for initial package restores (npm, pip, nuget) when tasks require it.
- Reproducible runs: deterministic settings (seed, temperature=0), pinned task fixtures.
- Model-agnostic via Ollama `/api/chat`.
- Easy to extend: adding tasks should be straightforward (a “task plugin” pattern).
- Produce artifacts suitable for CI and dashboards: JSON output + optional summary table.

### Non-goals

- Not a comprehensive “human eval” system.
- Not intended to benchmark multimodal features (even if models support vision).
- Not a general agent; it is a benchmark harness with strict IO protocols.

### High-level Flow

For each model M and task T:

1. Create an isolated temporary working directory.
2. Materialize the task repo (files, tests, configs).
3. Initialize `git` repo (optional but useful for debugging and capturing snapshots).
4. Run baseline tests; assert failure (ensures the task is valid).
5. Build a prompt containing:
   - file list
   - failing test output
   - full contents of relevant files
   - list of editable file paths (strict allow-list)
   - strict output format instructions
6. Call Ollama `/api/chat` with deterministic options:
   - `temperature=0`
   - `seed=<int>`
   - `num_ctx=<int>`
   - `num_predict=<int>` (kept modest to prevent rambling)
7. Parse the model response into one or more `BEGIN_FILE/END_FILE` blocks.
8. Validate:
   - all edited files are within the editable allow-list
   - content is non-empty and decodable
9. Apply edits by overwriting those files.
10. Run tests again.
11. Record results (pass/fail, timings, tok/s, error categories, etc.).

### System Components

#### 1) CLI Runner (`bench`)

Responsibilities:
- parse CLI args (models, tasks, ollama URL, output path, knobs)
- orchestrate model × task matrix
- collect, aggregate, and write results

Key flags (proposed):
- `--models ...`
- `--tasks ...` (or default suite)
- `--ollama-url http://127.0.0.1:11434/api/chat`
- `--num-ctx 16384`
- `--temperature 0`
- `--seed 1`
- `--num-predict 400`
- `--out results.json`
- `--format json|jsonl|table`
- `--keep-workdirs` (debug)

#### 2) Task Library (`tasks/`)

Each task provides:
- `name`
- `language` tag (node/python/dotnet)
- a `materialize(repo_dir)` function returning:
  - test command (argv list)
  - editable file allow-list
  - context file list to include in prompt
  - optional environment setup steps
- optional “warmup” hook for dependency restore caching

Tasks should be small, deterministic, and representative:
- Node: string sanitation, async behavior, edge-case parsing, small API refactor
- Python: correctness checks + regression tests
- .NET: SDK usage correctness + strict compilation + unit tests

#### 3) Prompt Builder (`prompting.py`)

Produces:
- system prompt (rules + output format)
- user prompt (repo metadata + failing output + file contents)

Must ensure:
- small enough to fit within `num_ctx`
- stable ordering
- explicit editable allow-list

#### 4) Model Adapter (`ollama_client.py`)

Encapsulates `/api/chat` call and extracts metrics:
- `wall_s`
- `prompt_eval_count`, `eval_count`
- `prompt_eval_duration`, `eval_duration`
- derived tokens/sec

#### 5) Output/Reporting (`reporting.py`)

Writes:
- `results.json` (or JSONL)
- optional markdown summary table:
  - pass rate by model/task
  - avg tok/s by model
  - failure breakdown (parse error vs invalid edit vs tests still failing)

### Data Model (Result Record)

Per run (model × task):

- `model`: string
- `task`: string
- `baseline_rc`: int
- `baseline_failed`: bool
- `edited_files`: list[string]
- `edit_parse_ok`: bool
- `edit_policy_ok`: bool
- `tests_pass`: bool
- `post_rc`: int
- `metrics`: object (from Ollama)
- `tok_per_s`: float|null
- `error_kind`: enum
  - `NO_BLOCKS`
  - `EDITED_NONEDITABLE_FILE`
  - `TESTS_STILL_FAIL`
  - `BASELINE_PASSED_INVALID_TASK`
  - `TOOL_ERROR`
- `error_detail`: string (truncated)

### Edit Protocol (Whole-file)

Model output must be:

BEGIN_FILE <relative/path>
<full updated file content>
END_FILE

Repeat blocks if editing multiple files.

Strictness:
- No extra text outside blocks.
- Only editable allow-list paths may appear.

### Security / Safety Notes

- Tasks run arbitrary code (tests). Only run trusted task suites.
- Use isolated temp directories.
- Consider running in a container for untrusted external repos.

### Extensibility Plan

- Add “external repo” mode:
  - clone a repo (local path provided)
  - run a defined failing test command
  - restrict editable allow-list (e.g., one file)
  - optionally provide a set of “benchmark scenarios” as YAML.

- Add “multiple trials” mode:
  - run each model/task N times with different seeds
  - report mean/variance.

### Known Constraints

- First run of npm/nuget may be slower due to restores.
- Models may violate formatting; harness should classify failures clearly.
- Large context windows increase KV cache; speed varies by model quant and VRAM spill.
