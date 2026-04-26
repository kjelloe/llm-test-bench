<<<<<<< HEAD
# llm-test-bench
Testing different models in a series of purposefully built tasks

Benchmarks local Ollama-served LLMs on coding tasks. Each model is given a broken file and must produce a corrected version using the `BEGIN_FILE / END_FILE` protocol. Tests determine pass/fail.

---

## Prerequisites

- [Ollama](https://ollama.com) running locally (`ollama serve`)
- Python 3.12+
- Node.js 20+
- .NET 8 SDK
- The models you want to test pulled (`ollama pull <model>`)

Run the preflight check to verify everything is in order:

```bash
./preflight.sh
```

Example output:

```
── GPU ──
  ✓  GPU: NVIDIA GeForce RTX 5060 Ti, 16311 MiB

── Ollama ──
  ✓  Ollama reachable at http://127.0.0.1:11434

── Ollama models ──
  ✓  qwen3-coder:30b
  ✓  qwen2.5-coder:14b
  ✓  gemma4:26b
  ✓  gpt-oss:120b
  ✓  qwen3.5:35b
  ✓  codestral:22b

── Python ──
  ✓  Python 3.12.3
  ✓  pytest 9.0.3

── Node.js ──
  ✓  node v20.20.2
  ✓  npm 10.8.2

── .NET ──
  ✓  dotnet 8.0.126

  PASS: 13   FAIL: 0   WARN: 1
  Preflight OK — ready to run ./compare.sh
```

---

## Quick start

### Run all benchmark models

```bash
./compare.sh
```

This runs all models defined in `bench-models.sh` (`qwen3-coder:30b`, `qwen2.5-coder:14b`, `codestral:22b`, `gemma4:26b`, `qwen3.5:35b`, `gpt-oss:120b`) against all eight tasks and writes results to `results-compare.json`.

The header printed before each run shows estimated runtime from the previous run, per-model history (last known pass rate and tok/s), and any **archived models** — models previously benchmarked but not in the current set. This means swapping a model out doesn't lose its history; it will reappear in the archived section on future runs.

### Run a single model

```bash
./run.sh --models qwen2.5-coder:7b
```

### Run a single model on a single task

```bash
./run.sh --models qwen2.5-coder:7b --tasks python_safe_div
```

### Run multiple models of your choosing

```bash
./run.sh --models qwen2.5-coder:7b gemma4:12b --out my-results.json
```

---

## Output

At the end of every run a comparison table is printed:

```
COMPARISON TABLE  (Spd: assumed rank 1=fastest  |  Skill: L1:2  L2:3  L3:3)
+-------------------+-----+-------+--------------------------+--------------------------+--  …  --+---------------------------+
| Model             | Spd | Skill | python_safe_div          | node_slugify             |   …     | pass  avg tok/s   tot s   |
|                   | est | L1-3  | (L1) ok  tok/s  wall     | (L2) ok  tok/s  wall     |   …     |                           |
+-------------------+-----+-------+--------------------------+--------------------------+--  …  --+---------------------------+
| qwen3-coder:30b   |  1  |  L3   | PASS    44.7t/s     7.0s | PASS    43.1t/s     9.3s |   …     | 8/8    39.5t/s     …s     |
| qwen2.5-coder:14b |  2  |  L2   | PASS    42.9t/s     6.5s | PASS    41.9t/s     7.2s |   …     | 7/8    41.8t/s     …s     |
+-------------------+-----+-------+--------------------------+--------------------------+--  …  --+---------------------------+

FAILURE DETAIL
  Model: qwen2.5-coder:14b
    TESTS_STILL_FAIL: 1
      e.g. TAP version 13 # Subtest: quoted field with escaped double-quote …
```

The **Skill** column shows the highest difficulty tier (L1–L3) where the model passes *all* tasks at that level and below.

Results are also written to JSON (`results.json` by default, `results-compare.json` for `compare.sh`).

---

## Tasks

Tasks are tagged with a difficulty level (L1–L3) used to compute the **Skill** rating in the results table.

| ID | Level | Language | What the model must fix |
|----|-------|----------|------------------------|
| `python_safe_div` | L1 | Python / pytest | `safe_div()` raises `ZeroDivisionError` instead of `ValueError` |
| `dotnet_sas` | L1 | .NET 8 / xUnit | Azure SAS token `ExpiresOn` is 10 min in the past instead of 60 min in the future |
| `node_slugify` | L2 | Node.js / ESM | `slugify()` in `src/slug.js` doesn't strip punctuation or collapse hyphens |
| `python_lru_cache` | L2 | Python / pytest | `LRUCache.get()` in `lru_cache.py` returns the value but doesn't promote the node to MRU, causing wrong eviction order |
| `node_csv_parser` | L3 | Node.js / ESM | `parseCSV()` in `src/csv.js` splits naively on commas — breaks on quoted fields containing commas or escaped quotes |
| `python_lfu_cache` | L3 | Python / pytest | `LFUCache._promote()` in `lfu_cache.py` doesn't update `min_freq` when a frequency bucket empties, causing `KeyError` on the next eviction |
| `python_bst_delete` | L3 | Python / pytest | `BST._delete()` in `bst.py` finds the in-order successor but discards the return value of the recursive delete, leaving a duplicate node in the tree |
| `python_multifile_rename` | L2 | Python / pytest | `price_cents` was renamed to `price` in `product.py` but two dependent files (`inventory.py`, `reports.py`) still use the old name — model must output **two** `BEGIN_FILE` blocks |

Baseline tests fail on the unmodified files. The model must output `BEGIN_FILE / END_FILE` blocks with the corrected file content, and tests must pass afterwards.

### Skill rating

The **Skill** column in the results table shows the highest difficulty tier where a model passes *all* tasks at that level and below:

| Rating | Meaning |
|--------|---------|
| `L3` | Passes all tasks (L1 + L2 + L3) |
| `L2` | Passes L1 + L2, fails at least one L3 task |
| `L1` | Passes L1 only, fails at least one L2 task |
| `<L1` | Fails at least one L1 task |

---

## All CLI options

```
python3 bench.py --help

  --models MODEL [MODEL ...]   Ollama model names (required)
  --tasks TASK_ID [...]        Subset of tasks (default: all)
                               Choices: node_slugify, python_safe_div, dotnet_sas,
                                        node_csv_parser, python_lru_cache,
                                        python_lfu_cache, python_bst_delete,
                                        python_multifile_rename
  --ollama-url URL             Default: http://localhost:11434
  --num-ctx INT                Context window tokens (default: 8192); individual tasks
                               may specify a higher minimum via Task.num_ctx
  --temperature FLOAT          Default: 0.0
  --seed INT                   Default: 1
  --num-predict INT            Max output tokens (default: 400)
  --model-timeout INT          Ollama HTTP request timeout in seconds (default: 300)
  --num-thread INT             CPU threads for Ollama inference; 0 = let Ollama decide
                               (default: 10 — limits heat without affecting GPU tok/s)
  --think                      Enable thinking/reasoning mode for supported models
  --warmup                     Send a tiny prompt to each model just before its first task
                               to force model load (JIT per model; uses keep_alive=-1 so
                               the model stays resident through all its own tasks;
                               enabled by default in compare.sh)
  --out FILE                   Results JSON path (default: results.json)
  --keep-workdirs              Don't delete temp workdirs (useful for debugging)
```

Extra flags passed to `compare.sh` or `run.sh` are forwarded to `bench.py`:

```bash
./compare.sh --num-ctx 16384 --num-predict 500
./compare.sh --tasks node_slugify python_safe_div
```

---

## Debugging a failure

Pass `--keep-workdirs` to inspect the state of the workdir after a run:

```bash
./run.sh --models deepseek-r1:32b --tasks dotnet_sas --keep-workdirs
# prints: workdir kept: /tmp/bench_dotnet_sas_abc123/
```

The workdir contains the files as the model left them. You can re-run the tests manually:

```bash
cd /tmp/bench_dotnet_sas_abc123
dotnet test
```

---

## Adding a task

1. Create `task_data/<your_task>/` with the baseline source file(s) and tests.
2. Verify the baseline tests **fail** (`node --test …` / `pytest` / `dotnet test` exits non-zero).
3. Add a `Task(…)` entry in `tasks.py` and register it in `BUILTIN_TASKS`.

See `ARCHITECTURE.md` for a complete example.
>>>>>>> 4ebc430 (Claude added README)
