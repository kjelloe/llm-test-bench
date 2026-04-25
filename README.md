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
  ✓  qwen2.5-coder:32b-instruct-q8_0
  ✓  gemma4:31b
  ✓  llama3.3:70b-instruct-q4_K_M
  ✓  deepseek-r1:32b

── Python ──
  ✓  Python 3.12.3
  ✓  pytest 9.0.3

── Node.js ──
  ✓  node v20.20.2
  ✓  npm 10.8.2

── .NET ──
  ✓  dotnet 8.0.126

  PASS: 11   FAIL: 0   WARN: 1
  Preflight OK — ready to run ./compare.sh
```

---

## Quick start

### Run all four benchmark models

```bash
./compare.sh
```

This runs `qwen2.5-coder:32b-instruct-q8_0`, `gemma4:31b`, `llama3.3:70b-instruct-q4_K_M`, and `deepseek-r1:32b` against all three tasks and writes results to `results-compare.json`.

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
COMPARISON TABLE
+----------------------------------+--------------------------+--------------------------+--------------------------+---------------------------+
| Model                            | node_slugify             | python_safe_div          | dotnet_sas               | pass  avg tok/s   tot s   |
|                                  | ok  tok/s  wall          | ok  tok/s  wall          | ok  tok/s  wall          |                           |
+----------------------------------+--------------------------+--------------------------+--------------------------+---------------------------+
| qwen2.5-coder:32b-instruct-q8_0  | PASS    42.3t/s    14.2s | PASS    44.1t/s     9.8s | FAIL    40.7t/s    22.1s | 2/3    42.4t/s     46.1s  |
| gemma4:31b                       | FAIL    38.9t/s    13.1s | PASS    41.2t/s     8.9s | PASS    39.5t/s    20.3s | 2/3    39.9t/s     42.3s  |
| llama3.3:70b-instruct-q4_K_M     | PASS    18.2t/s    28.4s | FAIL       -        5.1s | FAIL    17.8t/s    32.0s | 1/3    18.0t/s     65.5s  |
| deepseek-r1:32b                  | PASS    31.4t/s    16.3s | PASS    33.1t/s    10.2s | PASS    30.8t/s    24.7s | 3/3    31.8t/s     51.2s  |
+----------------------------------+--------------------------+--------------------------+--------------------------+---------------------------+

FAILURE DETAIL
  Model: llama3.3:70b-instruct-q4_K_M
    TOOL_ERROR: 1
    EDITED_NONEDITABLE_FILE: 1
      e.g. Edit to non-allowed file: 'tests/test_calc.py'
```

Results are also written to JSON (`results.json` by default, `results-compare.json` for `compare.sh`).

---

## Tasks

| ID | Language | What the model must fix |
|----|----------|------------------------|
| `node_slugify` | Node.js / ESM | `slugify()` in `src/slug.js` doesn't strip punctuation or collapse hyphens |
| `python_safe_div` | Python / pytest | `safe_div()` raises `ZeroDivisionError` instead of `ValueError` |
| `dotnet_sas` | .NET 8 / xUnit | Azure SAS token `ExpiresOn` is 10 min in the past instead of 60 min in the future |

Baseline tests fail on the unmodified files. The model must output `BEGIN_FILE / END_FILE` blocks with the corrected file content, and tests must pass afterwards.

---

## All CLI options

```
python3 bench.py --help

  --models MODEL [MODEL ...]   Ollama model names (required)
  --tasks TASK_ID [...]        Subset of tasks (default: all)
                               Choices: node_slugify, python_safe_div, dotnet_sas
  --ollama-url URL             Default: http://localhost:11434
  --num-ctx INT                Context window tokens (default: 8192)
  --temperature FLOAT          Default: 0.0
  --seed INT                   Default: 1
  --num-predict INT            Max output tokens (default: 400)
  --model-timeout INT          Ollama HTTP request timeout in seconds (default: 300)
  --think                      Enable thinking/reasoning mode for supported models
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
