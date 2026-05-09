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

Run the interactive installer to set up any missing dependencies:

```bash
./install.sh
```

Then run the preflight check to verify everything is in order:

```bash
./preflight.sh
```

To see which environment variables are set (Ollama URL, llama-server binary, GGUF directory, HF token, etc.) and how to configure them:

```bash
./configure.sh
```

Example output:

```
── GPU ──
  ✓  GPU: NVIDIA GeForce RTX 5060 Ti, 16311 MiB

── Ollama ──
  ✓  Ollama reachable at http://127.0.0.1:11434

── Ollama models ──
  ✓  gpt-oss:20b
  ✓  qwen2.5-coder:14b
  ✓  qwen3-coder:30b
  ✓  gemma4:26b
  ✓  qwen3.5:35b
  ✓  gpt-oss:120b

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

### Run the canonical benchmark (6 models)

```bash
./compare.sh
```

Runs all models defined in `models/default.txt` (`gpt-oss:20b`, `qwen2.5-coder:14b`, `qwen3-coder:30b`, `gemma4:26b`, `qwen3.5:35b`, `gpt-oss:120b`) against all twenty-four tasks. Writes results to `output/results-compare.json`.

### Run the extended benchmark (8 models)

```bash
./compare.sh extended
```

Runs all eight models evaluated to date (adds `codestral:22b` and `devstral-small-2`). Writes results to `output/results-extended.json`. Estimated runtime: 2.5–4 hours.

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

At the end of every run a comparison table is printed. When the full table would exceed the terminal width it automatically paginates, printing `[1/N]`, `[2/N]`, … headers:

```
COMPARISON TABLE [1/3]  (Spd: assumed rank 1=fastest  |  Skill: L1:6  L2:4  L3:5  L4:3  L5:2)
Hardware: RTX 5060 Ti 16GB  |  AMD Ryzen 7 5800X3D (16 logical cores)  |  64.0 GB RAM
+--------------------+-----+-------+--------------------------+--------------------------+--  …  --+--------------------------+---------------------------+
| Model              | Spd | Skill | python_safe_div          | node_slugify             |   …     | context_128k             | pass  avg tok/s   tot s   |
|                    | est | L1-3  | (L1) ok  tok/s  wall     | (L2) ok  tok/s  wall     |   …     | (L1) ok  tok/s  wall     |                           |
+--------------------+-----+-------+--------------------------+--------------------------+--  …  --+--------------------------+---------------------------+
| gpt-oss:20b        |  1  |  L3   | PASS    82.1t/s     8.3s | PASS    81.7t/s    23.4s |   …     | PASS  1574.0t/s    18.5s | 19/23   82.0t/s     …s    |
| qwen3-coder:30b    |  3  |  L3   | PASS    44.7t/s     7.0s | PASS    43.1t/s     9.3s |   …     | PASS   404.0t/s    62.0s | 21/23   39.5t/s     …s    |
+--------------------+-----+-------+--------------------------+--------------------------+--  …  --+--------------------------+---------------------------+

FAILURE DETAIL
  Model: gpt-oss:20b
    NO_BLOCKS: 2
      e.g. [thinking: We need to fix _promote to update min_freq … all 2400 tokens used for thinking]
    CTX_TRUNCATED: 2
      e.g. context_256k — Ollama capped num_ctx below 262144 (insufficient VRAM/RAM)
```

The **Skill** column shows the highest difficulty tier (L1–L5) where the model passes *all* tasks at that level and below. `CTX_TRUNCATED` failures (Ollama capping the context window due to VRAM/RAM limits) are treated as hardware constraints and excluded from the skill rating — they do not reduce a model's tier.

Results are also written to JSON (default: `output/results.json`; `output/results-compare.json` for `compare.sh`; `output/results-extended.json` for `compare.sh extended`).

### GPU telemetry

If `nvidia-ml-py` is installed (it is via `requirements.txt`), each result record includes:

- **`gpu_snapshots`** — three snapshots per model: `before_load` (taken after the previous model's weights drain from VRAM), `after_load` (after warmup), and `peak_during_gen` (highest `gpu_util` seen across 500ms polls during generation — captures peak activity even on sub-second tasks).
- **`kv_cache`** — VRAM delta before vs. after each `chat()` call, plus `kv_mb_per_1k_tokens` derived from the delta and total token count. Useful for comparing KV cache efficiency across quantizations.

The `before_load` snapshot includes a `"dirty": true` flag if VRAM did not drain to near-baseline within 10 seconds after the model unload request.

---

## Tasks

Tasks are tagged with a difficulty level (L1–L5) used to compute the **Skill** rating in the results table.

| ID | Level | Language | What the model must do |
|----|-------|----------|------------------------|
| `csv_nordic_property` | L3 | Python / pytest | Implement `solution.py` to answer 10 questions about a 5 000-row Norwegian property dataset (Nordic CSV: `;`-separated, UTF-8, `..` for missing values) and produce a filtered `output.csv` — bottom-25% and top-25% of regions by 2023 purchase sum, with only the 1992 and 2022 year-columns |
| `python_safe_div` | L1 | Python / pytest | `safe_div()` raises `ZeroDivisionError` instead of `ValueError` |
| `dotnet_sas` | L1 | .NET 8 / xUnit | Azure SAS token `ExpiresOn` is 10 min in the past instead of 60 min in the future |
| `node_slugify` | L2 | Node.js / ESM | `slugify()` in `src/slug.js` doesn't strip punctuation or collapse hyphens |
| `python_lru_cache` | L2 | Python / pytest | `LRUCache.get()` in `lru_cache.py` returns the value but doesn't promote the node to MRU, causing wrong eviction order |
| `python_multifile_rename` | L2 | Python / pytest | `price_cents` was renamed to `price` in `product.py` but two dependent files (`inventory.py`, `reports.py`) still use the old name — model must output **two** `BEGIN_FILE` blocks |
| `node_csv_parser` | L3 | Node.js / ESM | `parseCSV()` in `src/csv.js` splits naively on commas — breaks on quoted fields containing commas or escaped quotes |
| `python_lfu_cache` | L3 | Python / pytest | `LFUCache._promote()` in `lfu_cache.py` doesn't update `min_freq` when a frequency bucket empties, causing `KeyError` on the next eviction |
| `python_minheap` | L3 | Python / pytest | `MinHeap._sift_down()` in `minheap.py` checks the left child only — missing right-child comparison causes `pop()` to return elements out of order |
| `node_memoize_bug` | L3 | Node.js / ESM | `memoize()` in `src/memoize.js` builds its cache key from only the first argument — calls with the same first arg but different second arg return a stale cached result |
| `python_ledger_bug` | L4 | Python / pytest | `Ledger.transfer()` in `ledger.py` credits the destination account before checking the source balance — a failed transfer leaves the destination corrupted |
| `python_expr_eval` | L4 | Python / pytest | `Parser.expr()` and `Parser.term()` have their operator sets swapped — `*`/`/` are treated as low-precedence and `+`/`-` as high-precedence, inverting standard arithmetic precedence |
| `python_dijkstra` | L5 | Python / pytest | `dijkstra()` in `dijkstra.py` marks nodes visited when enqueued instead of when dequeued — shorter paths discovered later are silently ignored, producing wrong distances and paths |
| `python_hashmap` | L5 | Python / pytest | `HashMap.delete()` in `hashmap.py` clears slots directly instead of writing a tombstone — breaks linear-probe chains, causing `get()` to miss keys inserted after a colliding deletion |
| `context_8k` | L1 | Python / pytest | Find a sentinel value (`BENCHMARK_SENTINEL_VALUE`) at 50% depth in a ~5.5k-token Python stdlib archive; primary metric is prompt-eval tok/s at this context size |
| `context_16k` | L1 | Python / pytest | Same as context_8k at ~11k tokens |
| `context_32k` | L1 | Python / pytest | Same as context_8k at ~22k tokens |
| `context_64k` | L1 | Python / pytest | Same as context_8k at ~44k tokens |
| `context_128k` | L1 | Python / pytest | Same as context_8k at ~110k tokens (~440 KB real stdlib code); num_ctx=131072 |
| `context_256k` | L1 | Python / pytest | Same as context_8k at ~220k tokens (~880 KB real stdlib code); num_ctx=262144 — may CTX_TRUNCATE on models with insufficient VRAM/RAM |
| `multihop_forward` | L3 | Python / pytest | Two-hop retrieval: find engineer K. Vasquez in the archive (anchor at ~20%), carry name forward to locate a second incident at ~75% |
| `multihop_reverse` | L3 | Python / pytest | Same mechanic reversed: answer at ~20%, anchor at ~75% |
| `distractor_notes` | L2 | Python / pytest | Find INCIDENT-5000 header at ~50%; three decoy mentions in note bodies at ~15%, ~35%, ~70% — model must read the header field, not the notes |

Baseline tests fail on the unmodified files. The model must output `BEGIN_FILE / END_FILE` blocks with the corrected file content, and tests must pass afterwards.

### Skill rating

The **Skill** column in the results table shows the highest difficulty tier where a model passes *all* tasks at that level and below:

| Rating | Meaning |
|--------|---------|
| `L5` | Passes all tasks (L1 + L2 + L3 + L4 + L5) |
| `L4` | Passes L1 + L2 + L3 + L4, fails at least one L5 task |
| `L3` | Passes L1 + L2 + L3, fails at least one L4 task |
| `L2` | Passes L1 + L2, fails at least one L3 task |
| `L1` | Passes L1 only, fails at least one L2 task |
| `<L1` | Fails at least one L1 task |

`CTX_TRUNCATED` failures are excluded from this calculation — a model that could not process a large-context task due to VRAM/RAM limits is not penalised in its tier rating.

---

## All CLI options

```
python3 bench.py --help

  --models MODEL [MODEL ...]   Ollama model names (required)
  --tasks TASK_ID [...]        Subset of tasks (default: all)
                               Choices: csv_nordic_property,
                                        python_safe_div, dotnet_sas, node_slugify,
                                        python_lru_cache, python_multifile_rename,
                                        node_csv_parser, python_lfu_cache,
                                        python_minheap, node_memoize_bug,
                                        python_ledger_bug, python_expr_eval,
                                        python_tokenizer, python_dijkstra,
                                        python_hashmap, context_8k, context_16k,
                                        context_32k, context_64k, context_128k,
                                        context_256k, multihop_forward,
                                        multihop_reverse, distractor_notes
  --backend ollama|llama-server  Inference backend (default: ollama; env: BENCH_BACKEND)
  --model-file PATH            models/*.txt file for GGUF/param lookup (required for
                               llama-server backend; compare.sh passes it automatically)
  --ollama-url URL             Default: http://localhost:11434 (ollama backend only)
  --num-ctx INT                Context window tokens (default: 8192); individual tasks
                               may specify a higher minimum via Task.num_ctx
  --temperature FLOAT          Default: 0.0
  --seed INT                   Default: 1
  --num-predict INT            Max output tokens (default: 400; compare.sh sets 4800 for
                               thinking models that burn tokens on reasoning before BEGIN_FILE)
  --model-timeout INT          Ollama HTTP request timeout in seconds (default: 300)
  --startup-timeout INT        Seconds to wait for llama-server to become ready (default: 600;
                               large RAM-bound models like gpt-oss:120b with mlock take 300–600s)
  --num-thread INT             CPU threads for inference; 0 = let backend decide
                               (default: 10; passed as --threads to llama-server)
  --think                      Enable thinking/reasoning mode (ollama only; no-op for
                               llama-server which does not expose the think API)
  --warmup                     Send a tiny prompt before the first task to force model
                               load (ollama only; no-op for llama-server — model loads
                               during server startup; enabled by default in compare.sh)
  --out FILE                   Results JSON path (default: output/results.json)
  --keep-workdirs              Don't delete temp workdirs (useful for debugging)
```

---

## llama-server backend

To benchmark using [llama.cpp](https://github.com/ggerganov/llama.cpp)'s `llama-server` instead of Ollama (useful for MoE-specific parameters like `--n-cpu-moe`):

1. Set `LLAMA_MODELS_DIR` to your GGUF directory:
   ```bash
   export LLAMA_MODELS_DIR=/path/to/gguf/models
   ```

2. Add GGUF filenames (and optional params) to `models/default.txt`:
   ```
   # ollama-name  [gguf-file  [key=val,flag,...]]
   gpt-oss:20b
   qwen2.5-coder:14b  qwen2.5-coder-14b-Q4_K_M.gguf
   qwen3.5:35b        qwen3.5-35b-A22B-Q4_K_M.gguf    n_cpu_moe=35,no_mmap,mlock,cache_type_k=q8_0,cache_type_v=q8_0
   ```
   Models with no GGUF filename can only run on Ollama; they will error immediately if selected with `--backend llama-server`.

   > **Note on KV cache types:** `turbo4`/`turbo3` are not supported by all llama.cpp builds. Use `q8_0` for broad compatibility.

3. Run with the llama-server backend:
   ```bash
   ./compare.sh --backend llama-server
   # or: BENCH_BACKEND=llama-server ./compare.sh
   ```
   `compare.sh` automatically passes `--model-file` when reading a named model set.

**Startup timeout:** Large RAM-bound models (e.g. `gpt-oss:120b` with `mlock`) can take 300–600 seconds to load from disk. The harness waits up to `--startup-timeout` seconds (default 600) for `/health` to return `{"status":"ok"}`. If the server exits before that, its full stderr is printed for diagnosis.

**Context window handling:** `--ctx-size` is a startup flag for llama-server, not per-request. The harness starts the server at the required context size and restarts it automatically if a subsequent task needs a larger window (e.g. `context_128k` needs 131072 tokens). A server running at a larger context is reused for smaller tasks — it never downsizes mid-model.

**CTX_TRUNCATED recovery:** If a task returns `CTX_TRUNCATED` (server silently capped the context because VRAM was insufficient), the harness stops the llama-server immediately so the next task gets a clean restart rather than hanging against an undersized server.

**Timing:** `tok_per_s` for llama-server uses llama.cpp's `timings.predicted_ms` field (generation phase only, same precision as Ollama). Falls back to `completion_tokens / wall_time` on older builds that omit `timings`.

**Comparing backends side by side:** `compare.sh` auto-names output files by backend (`results-compare.json` for ollama, `results-compare-ls.json` for llama-server). Use `compare-results.sh` to merge and compare them:

```bash
./compare.sh                        # → output/results-compare.json
./compare.sh --backend llama-server # → output/results-compare-ls.json
./compare-results.sh output/results-compare.json output/results-compare-ls.json
```

The comparison prints a speed summary (avg tok/s, total wall time, speedup %) per model per backend, followed by the full per-task table with `model [ollama]` and `model [ls]` as separate rows.

Extra flags passed to `compare.sh` or `run.sh` are forwarded to `bench.py`:

```bash
./compare.sh --num-ctx 16384 --num-predict 500
./compare.sh --tasks node_slugify python_safe_div
```

---

## Downloading GGUF models

`fetch-hf.sh` downloads GGUF files from HuggingFace Hub into `$LLAMA_MODELS_DIR`. `search-hf.sh` searches the Hub and suggests the best file and `models/*.txt` line to paste.

Add an `hf:` field to any model line (position-independent after the ollama name):

```
qwen2.5-coder:14b  Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf  hf:bartowski/Qwen2.5-Coder-14B-Instruct-GGUF
gpt-oss:120b       gpt-oss-120b-mxfp4-00001-of-00003.gguf   hf:ggml-org/gpt-oss-120b-GGUF
```

```bash
# Search for models not yet configured in models/default.txt
./search-hf.sh --model-files models/default.txt

# Search for a specific model
./search-hf.sh "qwen2.5 coder 14b"

# Show top pick per model only in summary (--limit N repos shown, --max-files N files per repo)
./search-hf.sh --top-only --limit 3

# Download all models with hf: fields (requires $LLAMA_MODELS_DIR to be set)
./fetch-hf.sh

# Preview without downloading
./fetch-hf.sh --dry-run

# Download a specific model only
./fetch-hf.sh --models qwen2.5-coder:14b
```

Multi-shard models (e.g. `gpt-oss-120b-mxfp4-00001-of-00003.gguf`) are detected automatically — give `fetch-hf.sh` the shard-1 filename and it downloads all parts.

Requires `huggingface_hub` (included in `requirements.txt`; installed when you first run `./run.sh`).

---

## Exporting results

`statistics.sh` aggregates all `output/*.json` result files into a flat dataset for comparison across hardware or model versions.

```bash
# Markdown table to stdout (default)
./statistics.sh

# One row per model (summary — pass rate, avg tok/s, skill breakdown)
./statistics.sh --format markdown

# One row per task (detailed)
./statistics.sh --detail --format csv --out stats.csv

# JSON array for programmatic processing
./statistics.sh --format json --out stats.json

# Process a specific file only
./statistics.sh output/results-compare-ls.json --format markdown
```

**Summary mode** (default) produces one row per `(model, backend)` with: hardware identifiers, pass rate, avg tok/s, total wall time, per-level skill breakdown (e.g. `L1:6/6  L2:4/5  L3:3/3`), and error kind counts.

**Detail mode** (`--detail`) produces one row per `(model, task)` with: all hardware fields, task difficulty, pass/fail, error kind, tok/s, wall_s, prompt tokens, gen tokens, num_ctx, and truncation flags.

Hardware fields exported: GPU name+VRAM, GPU driver, free VRAM at run start, GPU temperature, GPU power limit, CPU, RAM, platform, CUDA toolkit version, llama-server version (if applicable), Ollama version (if applicable), and storage device type.

The CSV format uses `;` as delimiter with all cells double-quoted (Nordic CSV — compatible with Excel on Nordic locales).

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

