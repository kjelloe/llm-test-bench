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
  ✓  qwen3.5:122b
  ✓  llama3.3:70b-instruct-q4_K_M

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

This runs all models defined in `bench-models.sh` (`qwen3-coder:30b`, `qwen2.5-coder:14b`, `gemma4:26b`, `gpt-oss:120b`, `qwen3.5:122b`, `llama3.3:70b-instruct-q4_K_M`) against all five tasks and writes results to `results-compare.json`.

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
COMPARISON TABLE  (Spd: assumed rank 1=fastest)
+------------------------------+-----+--------------------------+--------------------------+--------------------------+--------------------------+--------------------------+---------------------------+
| Model                        | Spd | node_slugify             | python_safe_div          | dotnet_sas               | node_csv_parser          | python_lru_cache         | pass  avg tok/s   tot s   |
|                              | est | ok  tok/s  wall          | ok  tok/s  wall          | ok  tok/s  wall          | ok  tok/s  wall          | ok  tok/s  wall          |                           |
+------------------------------+-----+--------------------------+--------------------------+--------------------------+--------------------------+--------------------------+---------------------------+
| qwen3-coder:30b              |  1  | PASS    46.1t/s    10.4s | PASS    52.2t/s     6.4s | PASS    45.1t/s    11.3s | PASS    47.2t/s     5.5s | PASS    43.8t/s    14.1s | 5/5    46.9t/s     47.7s  |
| qwen2.5-coder:14b            |  2  | PASS    42.7t/s    11.0s | PASS    41.8t/s     6.5s | PASS    41.6t/s     9.4s | FAIL    41.9t/s     5.3s | PASS    41.8t/s    13.7s | 4/5    42.0t/s     45.9s  |
| llama3.3:70b-instruct-q4_K_M |  3  | PASS     1.7t/s    94.1s | PASS     1.8t/s    45.4s | PASS     1.7t/s   104.8s | PASS     1.7t/s   130.7s | PASS     1.7t/s   222.1s | 5/5     1.7t/s    597.1s  |
+------------------------------+-----+--------------------------+--------------------------+--------------------------+--------------------------+--------------------------+---------------------------+

FAILURE DETAIL
  Model: qwen2.5-coder:14b
    TESTS_STILL_FAIL: 1
      e.g. TAP version 13 # Subtest: simple unquoted row ok 1 ...
```

Results are also written to JSON (`results.json` by default, `results-compare.json` for `compare.sh`).

---

## Tasks

| ID | Language | What the model must fix |
|----|----------|------------------------|
| `node_slugify` | Node.js / ESM | `slugify()` in `src/slug.js` doesn't strip punctuation or collapse hyphens |
| `python_safe_div` | Python / pytest | `safe_div()` raises `ZeroDivisionError` instead of `ValueError` |
| `dotnet_sas` | .NET 8 / xUnit | Azure SAS token `ExpiresOn` is 10 min in the past instead of 60 min in the future |
| `node_csv_parser` | Node.js / ESM | `parseCSV()` in `src/csv.js` splits naively on commas — breaks on quoted fields containing commas or escaped quotes |
| `python_lru_cache` | Python / pytest | `LRUCache.get()` in `lru_cache.py` returns the value but doesn't promote the node to MRU, causing wrong eviction order |

Baseline tests fail on the unmodified files. The model must output `BEGIN_FILE / END_FILE` blocks with the corrected file content, and tests must pass afterwards.

---

## All CLI options

```
python3 bench.py --help

  --models MODEL [MODEL ...]   Ollama model names (required)
  --tasks TASK_ID [...]        Subset of tasks (default: all)
                               Choices: node_slugify, python_safe_div, dotnet_sas,
                                        node_csv_parser, python_lru_cache
  --ollama-url URL             Default: http://localhost:11434
  --num-ctx INT                Context window tokens (default: 8192)
  --temperature FLOAT          Default: 0.0
  --seed INT                   Default: 1
  --num-predict INT            Max output tokens (default: 400)
  --model-timeout INT          Ollama HTTP request timeout in seconds (default: 300)
  --think                      Enable thinking/reasoning mode for supported models
  --warmup                     Send a tiny prompt to each model before benchmarking
                               to force model load; eliminates cold-start wall-time
                               penalty on the first task (enabled by default in compare.sh)
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
