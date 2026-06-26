# llm-test-bench
Testing different models in a series of purposefully built tasks

Benchmarks local Ollama-served LLMs on coding tasks. Each model is given a broken file and must produce a corrected version using the `BEGIN_FILE / END_FILE` protocol. Tests determine pass/fail.

---

## Prerequisites

- [Ollama](https://ollama.com) running locally (`ollama serve`)
- Python 3.12+
- Node.js 20+
- .NET 9 SDK
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
  ✓  noctrex-qwen3.6:35b
  ✓  gpt-oss:20b
  ✓  qwen2.5-coder:14b
  ✓  qwen3-coder:30b-1m
  ✓  gemma4:26b
  ✓  qwen3.5:35b
  ✓  gpt-oss:120b
  ✓  devstral-small-2

── Python ──
  ✓  Python 3.12.3
  ✓  pytest 9.0.3

── Node.js ──
  ✓  node v20.20.2
  ✓  npm 10.8.2

── .NET ──
  ✓  dotnet 9.0.17

  PASS: 13   FAIL: 0   WARN: 1
  Preflight OK — ready to run ./compare.sh
```

---

## Quick start

### Run the canonical benchmark (9 models)

```bash
./compare.sh
```

Runs all models defined in `models/default.txt` (`noctrex-qwen3.6:35b`, `gpt-oss:20b`, `qwen2.5-coder:14b`, `qwen3-coder:30b-1m`, `gemma4:26b`, `qwen3.5:35b`, `gpt-oss:120b`, `devstral-small-2`, `qwen3.6:27b`) against all thirty-three tasks (19 coding, 4 L6 stepped, 1 L6 full, 6 context, 3 multihop). Writes results to `output/results-compare.json`.

### Run the extended benchmark (10 models)

```bash
./compare.sh extended
```

Runs the 7 default models plus `codestral:22b`, `phi4-reasoning-plus:14b`, and `llama4-scout:17b`. Note: `phi4-reasoning-plus` is incompatible (loops in reasoning planning phase and never emits BEGIN_FILE regardless of token budget); `llama4-scout` runs at ~3.3 tok/s (CPU-bound on 24 GB). Writes results to `output/results-extended.json`.

The header printed before each run shows estimated runtime from the previous run, per-model history (last known pass rate and tok/s), and any **archived models** — models previously benchmarked but not in the current set. This means swapping a model out doesn't lose its history; it will reappear in the archived section on future runs.

### Run a single model

```bash
./run.sh --models qwen2.5-coder:7b
```

### Run a single model on a single task

```bash
./run.sh --models qwen2.5-coder:7b --tasks python_safe_div
```

### Run only coding tasks (or context / multihop)

```bash
# 15 coding tasks only (useful for large RAM-bound models where context tasks are impractical)
./compare.sh --task-group coding
./run.sh --models qwen2.5-coder:7b --task-group coding

# 4 stepped L6 Paratrooper tasks (incremental difficulty; solvable without thinking mode)
./compare.sh --task-group l6

# Full L6 (implement entire Paratrooper game from scratch; needs thinking model + large token budget)
./compare.sh --task-group l6_full

# 6 context-retrieval tasks only
./compare.sh --task-group context

# 3 multihop + distractor tasks only
./compare.sh --task-group multihop

# Combine groups
./compare.sh --task-group coding l6
./compare.sh --task-group coding multihop
```

`--task-group` and `--tasks` are mutually exclusive.

### Run multiple models of your choosing

```bash
./run.sh --models qwen2.5-coder:7b gemma4:12b --out my-results.json
```

---

## Benchmark results

All results use the **llama-server backend**, RTX 4090 24 GB + RTX 3090 24 GB, AMD Ryzen 9 9900X, 86 GB RAM. Temperature=0, seed=1, num-predict=8000, model-timeout=1200.

### Default set — 33 tasks (2026-06-24; llama-server, 2×24 GB, 4 models × 33 tasks)

| Model | Pass | Avg tok/s | Skill | Notes |
|---|---|---|---|---|
| noctrex-qwen3.6:35b | **32/33** | 121 | L5 | MXFP4 MoE; 19/19 coding PERFECT; context_128k PASS 89 tok/s; node_paratrooper FAIL (universal wall) |
| qwen3.6:27b | **32/33** | 40 | L5 | Dense 27B Q4_K_M; f16 KV required; 19/19 coding PERFECT; context_128k PASS; node_paratrooper FAIL |
| quest:35b | 29/33 | 132 | L1 | noctrex RL-trained MXFP4 MoE; python_multifile_rename (L2) caps skill; passes both L5 + node_para_combat (L6) |
| qwen3-next:80b | 29/33 | 109 | L2 | noctrex MXFP4 MoE 80B/A3B; ~115 tok/s at 16k ctx; fails node_para_core/entities; context_256k OOM |

node_paratrooper (l6_full) uses `num_predict=8000` in compare.sh — insufficient for the 40-test game (needs 24000). All models fail it at 8000 tokens; this is a budget constraint, not a capability ceiling. MoE models maintain high tok/s at large contexts due to minimal KV overhead; dense models spill at 128k.

### Earlier default-set run — 33 tasks (2026-05-25; llama-server, RTX 3090 24 GB, 8 models)

| Model | Pass | Avg tok/s | Skill | Notes |
|---|---|---|---|---|
| gpt-oss:120b | **31/33** | 16 | L5 | RAM-bound (~1 tok/s coding); csv_nordic_property + node_paratrooper FAIL; all L6 stepped PASS |
| qwen3-coder:30b-1m | 30/33 | 150 | L4 | 1M-ctx MoE; 19/19 coding PERFECT; context_128k SLOW 3.3 tok/s; node_para_entities + node_paratrooper FAIL |
| qwen3.5:35b | 30/33 | 135 | L2 | MoE 35B/3B active; python_hashmap + csv_nordic_property + node_paratrooper FAIL |
| gemma4:26b | 29/33 | 105 | L2 | MoE 26B/4B active; csv_nordic_property + node_para_entities + node_paratrooper FAIL |
| devstral-small-2 | 29/33 | 40 | L1 | Dense 24B; node_slugify + node_para_entities + node_paratrooper FAIL |
| qwen2.5-coder:14b | 23/33 | 72 | L2 | Dense 14B Q4_K_M ~9 GB; ctx silently capped at 32k; passes both L5 coding tasks; fails csv_nordic_property + node_csv_parser (L3 parsing) |
| gpt-oss:20b | **22/33** | 181 | **<L1** | Semi-thinking: verbose reasoning exhausts 8k budget on L4/L5 tasks; non-deterministic between runs |

### Experimental models (llama-server, single RTX 4090 unless noted)

| Model | Pass | Avg tok/s | Notes |
|---|---|---|---|
| mellum2:12b-thinking | 20/33 | 254 | MXFP4 MoE A2.5B active ~6.5 GB; 8 GB tier; Skill L1 (node_slugify L2 FAIL); FASTEST model benchmarked; passes node_para_core (L3) + node_csv_parser; python_hashmap NO_BLOCKS (thinking budget ceiling at any token count); ctx≤32k |
| glm4.7-flash | **29/33** | 111 | MXFP4 MoE ~16 GB; Skill L4; 2026-06-26 full run; passes all L1–L4 + node_para_entities (L5) + node_para_combat (L6); fails python_hashmap + python_dijkstra (L5 capability gap) + context_256k (wrong answer); added to 24gb.txt |
| qwen2.5-coder:14b | 23/33 | 72 | Dense 14B Q4_K_M ~9 GB; Skill L2; ctx silently capped at 32k (q8_0 KV on 24 GB GPU = real 12 GB card behavior); passes both L5 coding tasks (hashmap + dijkstra); fails csv_nordic_property + node_csv_parser (L3 parsing) |
| qwen2.5-coder:32b-q4 | **28/33** | 36.5 | Dense 32B Q4_K_M ~18.5 GB; Skill L2; 2026-06-26 full run (2×24 GB); **19/19 coding PERFECT** (strongest coder tested; passes python_expr_eval, csv_nordic, node_csv_parser); passes para L4/L5/L6 stepped; FAILS node_para_core (L3 logic gap); ctx caps at 32k even on 48 GB; added to 24gb.txt |
| qwen3-coder:30b (base) | 30/33 | 160 | Superseded by 1M variant; same L6 ceiling; slower on all tasks |
| qwen3.6:35b-A3B | 25/29 | 134 | Q4_K_M MoE; passes python_hashmap + python_expr_eval; node_csv_parser blind spot |
| nemotron-nano:30b-a3b | 16/19 coding | 176 | Mamba-2 hybrid; passes python_expr_eval; consistent 3-task fails: node_slugify (L2) + python_dijkstra + python_hashmap (L5); max_ctx=65536 |
| deepseek-r1:32b | 18/19 coding | 31 | context_64k+ SKIPPED (max_ctx=32768); python_expr_eval NO_BLOCKS (reasoning spiral — confirmed capability gap, not token budget) |
| carnice:35b | 17/19 coding | 41 | MTP fine-tune coding-only (full run 27 tok/s, 96 min); csv_nordic_property FAIL wrong answers; python_merge_intervals NO_BLOCKS at 8000 tokens; context_128k SLOW 6.2 tok/s |
| north-mini-code | 6/10 subset | 141 | Cohere 30B MoE 3B active Q4_K_M; passes python_hashmap (L5); format non-compliant on complex tasks — agentic training preamble exhausts budget before BEGIN_FILE; rejected |

### L6 Paratrooper — from-scratch (node_paratrooper, num_predict=24000, 2026-05-20)

| Model | Score | Notes |
|---|---|---|
| noctrex-qwen3.6:35b | **39/40** | MXFP4+MTP; 36s — ties best; fails only test 33 (freefall crush) |
| qwen3.6:35b-A3B | **39/40** | Non-thinking; 4.2k tokens, 35s — most efficient; fails only test 33 |
| gemma4:26b | **39/40** | Non-thinking; fails only test 33 (freefall crush) |
| devstral-small-2 | 38/40 | Non-thinking; fails test 33 + test 35 |
| qwen3.5:35b | 38/40 | Thinking; fails test 18 (spawn timing) + test 33 |
| deepseek-r1:32b | 32/40 | Thinking |
| qwen3-coder:30b | 0/40 | Constructor broken; 15/15 on coding ≠ from-scratch architecture |
| nemotron-nano:30b | 0/40 | ES module export failure (no `export` keyword on class) |

Run with `--task-group l6_full --num-predict 24000 --model-timeout 1800`. compare.sh default (8000 tokens) is insufficient. Test 33 is the universal failure wall across all models. **Thinking does not help** — non-thinking gemma4 and devstral outperform thinking qwen3.5.

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
| qwen3-coder:30b-1m |  3  |  L4   | PASS    44.7t/s     7.0s | PASS    43.1t/s     9.3s |   …     | PASS   404.0t/s    62.0s | 21/23   39.5t/s     …s    |
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

Tasks are tagged with a difficulty level (L1–L6) used to compute the **Skill** rating in the results table.

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
| `python_tokenizer` | L4 | Python / pytest | After processing an escape sequence inside a string, the tokenizer transitions back to the wrong state — characters following any escape sequence are emitted as `WORD`/`UNKNOWN` tokens outside the string instead of being part of the `STRING` token |
| `python_dijkstra` | L5 | Python / pytest | `dijkstra()` in `dijkstra.py` marks nodes visited when enqueued instead of when dequeued — shorter paths discovered later are silently ignored, producing wrong distances and paths |
| `python_hashmap` | L5 | Python / pytest | `HashMap.delete()` in `hashmap.py` clears slots directly instead of writing a tombstone — breaks linear-probe chains, causing `get()` to miss keys inserted after a colliding deletion |
| `node_debounce` | L3 | Node.js / ESM | `debounce()` in `src/debounce.js` should coalesce rapid calls into one delayed invocation — it does not; model must diagnose why cancellation never works |
| `python_merge_intervals` | L4 | Python / pytest | `merge_intervals()` in `merge_intervals.py` returns wrong results for certain interval patterns; silent wrong-output bug — model must identify the incorrect case |
| `awk_csv_stats` | L3 | AWK / pytest | `stats.awk` should print per-region sales totals from a comma-separated CSV — output is wrong; model must identify the misconfiguration |
| `java_word_freq` | L3 | Java / pytest | `WordFreq.topK()` in `WordFreq.java` should return the k most frequent words in descending order — returns the wrong words; model must find the ordering bug |
| `node_para_core` | L6 | Node.js / ESM | **Paratrooper step 1/4** — implement the `Game` constructor, input processing, tick counter, isOver/getResult/getState; seeded mulberry32 RNG; 7 tests |
| `node_para_turret` | L6 | Node.js / ESM | **Paratrooper step 2/4** — add turret rotation (`_processInput`) and projectile physics (`_updateProjectiles`: `rad=(180-angle)×π/180`, `dx=cos(rad)×speed`, `dy=-sin(rad)×speed`); 17 cumulative tests |
| `node_para_entities` | L6 | Node.js / ESM | **Paratrooper step 3/4** — add helicopter spawning/movement, paratrooper descent (chute → freefall → landed states), and overrun lose condition; 29 cumulative tests |
| `node_para_combat` | L6 | Node.js / ESM | **Paratrooper step 4/4** — add jets, bombs, and full collision detection (projectile/bomb vs all entity types); 40 cumulative tests (complete suite) |
| `node_paratrooper` | L6 | Node.js / ESM | **Full Paratrooper** (for `--task-group l6_full`) — implement the entire `Game` class from scratch; all 40 tests; requires a thinking model with large token budget |
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

### Task catalog

Each task is a realistic bug pattern a developer might encounter. The model sees only the broken file and the test suite — no hint about what is wrong.

#### Coding — Python

**`python_safe_div` (L1)** — A one-line fix: the function raises the wrong exception type (`ZeroDivisionError` instead of `ValueError`). Tests catch the specific type. Easy warm-up.

**`python_lru_cache` (L2)** — `get()` returns the correct value but silently skips promoting the node to the most-recently-used position. The eviction order is wrong as a result. Requires understanding the doubly-linked list invariant, not just the map lookup.

**`python_multifile_rename` (L2)** — A field was renamed in one file but two dependent modules still use the old name. The model must output two `BEGIN_FILE` blocks — one per file. Tests the ability to track a rename across a small codebase.

**`python_lfu_cache` (L3)** — The LFU eviction policy has a subtle invariant bug in `_promote()`: it doesn't update `min_freq` when a frequency bucket empties. The cache works most of the time but crashes with `KeyError` on the next eviction after a specific access pattern.

**`python_minheap` (L3)** — `_sift_down()` only compares against the left child, ignoring the right. The heap property is violated after `pop()` on certain inputs. A missing two-line right-child check.

**`python_ledger_bug` (L4)** — A classic atomicity bug: the destination account is credited before the source balance is checked, so a failed transfer leaves money credited to the destination but not debited from the source. Requires understanding the correct order of operations for transactional state updates.

**`python_expr_eval` (L4)** — The recursive descent parser has `expr()` and `term()` with their operator sets swapped: `*`/`÷` are treated as low precedence and `+`/`-` as high. `2 + 3 * 4` evaluates to 20 instead of 14. Requires understanding how precedence climbing works through mutual recursion.

**`python_tokenizer` (L4)** — After processing an escape sequence (`\n`, `\t`, etc.) inside a string literal, the state machine jumps back to the default state instead of staying inside the string. Characters after an escape are tokenised as `WORD` tokens outside the string rather than continuing the `STRING` token.

**`python_dijkstra` (L5)** — Nodes are marked visited when added to the priority queue instead of when popped. This means a shorter path discovered later is discarded because the node is already marked. Produces wrong shortest distances and paths on graphs with multiple routes to a node.

**`python_hashmap` (L5)** — Open-addressing hash map: `delete()` clears the slot directly instead of writing a tombstone sentinel. This breaks the linear-probe chain — a `get()` for a key inserted after a collision stops at the empty slot and reports the key as missing.

**`python_merge_intervals` (L4)** — `merge_intervals()` should return a minimal non-overlapping sorted list, but returns wrong results for certain inputs. The bug is silent — no crash, just subtly wrong output on specific interval patterns. The model must identify which case is handled incorrectly and fix it.

**`csv_nordic_property` (L3)** — Implement `solution.py` from scratch to answer 10 questions about a 5 000-row Norwegian property dataset (semicolon-separated, UTF-8, `..` for nulls) and produce a filtered CSV. Tests multi-step data analysis: filtering, aggregation, sorting, and output formatting. Consistently fails models that struggle with multi-step reasoning over real tabular data.

#### Coding — JavaScript / Node.js

**`node_slugify` (L2)** — The slug function lowercases and replaces spaces, but doesn't strip apostrophes silently (`it's` → `its`, not `it-s`) or collapse multiple non-alphanumeric characters into a single hyphen. Tests require exact output on several tricky inputs.

**`node_csv_parser` (L3)** — The parser splits every line on commas without checking whether a comma is inside a quoted field. Fields containing commas, escaped double-quotes (`""`), or empty quoted fields all parse incorrectly. A complete RFC 4180-style parser is required.

**`node_memoize_bug` (L3)** — The cache key is built from the first argument only. When two calls share the same first argument but differ on the second (e.g. `applyDiscount(price, 10)` vs `applyDiscount(price, 20)`), the second call returns the cached result of the first. A one-line fix: include all arguments in the key.

**`node_debounce` (L3)** — `debounce()` in `src/debounce.js` should coalesce rapid calls into a single delayed invocation, but rapid successive calls each fire independently. The model must read the implementation, identify why cancellation never works, and fix it. Tests use real millisecond-range timers.

#### Coding — .NET

**`dotnet_sas` (L1)** — Azure SAS token generation: `ExpiresOn` is set with `AddMinutes(-10)` (10 minutes in the past) instead of `AddMinutes(60)`. One integer sign change. Validates that the model can apply a targeted edit without touching unrelated code.

#### Coding — Java

**`java_word_freq` (L3)** — `WordFreq.topK(int k)` should return the k most frequent words in descending order, but returns the wrong words. The model must identify the ordering bug in the implementation and fix it. Tests cover multi-add accumulation, case folding, and punctuation delimiters.

#### Coding — AWK

**`awk_csv_stats` (L3)** — `stats.awk` should print per-region sales totals from a comma-separated CSV, but produces wrong output. The model must inspect the script, identify the misconfiguration, and fix it.

---

#### L6 — Paratrooper (stepped and full)

A headless JavaScript backend for the 1982 arcade game *Paratrooper*, split into four steps of increasing complexity plus a full from-scratch variant. Each step adds one subsystem; subsequent steps include the reference implementation from all prior steps, so the model only needs to implement the new methods.

**`node_para_core` (L6, step 1/4)** — Constructor, tick counter, state fields, input queue, `isOver()`, `getResult()`, `getState()`. Foundation layer; 7 tests.

**`node_para_turret` (L6, step 2/4)** — Turret rotation (clamp to 0–180°) and projectile physics using the firing formula `rad = (180 − angle) × π/180`. 17 cumulative tests.

**`node_para_entities` (L6, step 3/4)** — Helicopter spawning and movement, paratrooper descent through chute → freefall → landed states, overrun lose condition. The real difficulty wall: only the strongest models pass this step without the full scaffolding. 29 cumulative tests.

**`node_para_combat` (L6, step 4/4)** — Jets, falling bombs, and collision detection between projectiles/bombs and all entity types (helicopters, jets, paratroopers, turret). 40 cumulative tests (the complete suite).

**`node_paratrooper` (L6, from scratch)** — Implement the entire `Game` class from a spec and stub comments, with no prior-step reference. Run separately with `--task-group l6_full --num-predict 24000`. Best scores to date: 39/40 (qwen3.6:35b-A3B and gemma4:26b). Test 33 — a freefall paratrooper crushing landed troops on landing — has not been passed by any model despite the rule being explicit in the stub.

---

#### Context retrieval

Six tasks at increasing context depths (8k → 256k tokens) ask the model to find a specific sentinel value buried in a Python standard library archive. The task itself is trivially easy at short context; it measures raw retrieval reliability and generation speed (tok/s) as the context grows.

**`context_8k` / `context_16k` / `context_32k` / `context_64k` / `context_128k` / `context_256k` (L1)** — Find `BENCHMARK_SENTINEL_VALUE` at 50% depth in archives ranging from ~5.5k to ~220k tokens. Speed collapses at 128k+ for models whose KV cache overflows VRAM. `context_256k` is skipped automatically on 24 GB cards (`min_vram_gb=48`).

---

#### Multihop retrieval

**`multihop_forward` (L3)** — Two-hop retrieval in a ~30k-token incident archive. Anchor: engineer K. Vasquez at ~20% depth. The model must carry the name forward and find her second incident at ~75% depth. The answer is never stated directly — it requires connecting two records.

**`multihop_reverse` (L3)** — Same two-hop mechanic in reverse: anchor at ~75%, second incident at ~20%. Harder for models that scan forward and stop at the anchor.

**`distractor_notes` (L2)** — Find `INCIDENT-5000`'s resolution code in a ~30k-token archive. Three decoy mentions of the same code appear in note bodies at ~15%, ~35%, and ~70% depth. The model must read the structured header field, not the prose notes. Tests whether the model is fooled by repeated distractor context.

### Skill rating

The **Skill** column in the results table shows the highest difficulty tier where a model passes *all* tasks at that level and below:

| Rating | Meaning |
|--------|---------|
| `L6` | Passes all tasks (L1 + L2 + L3 + L4 + L5 + L6) |
| `L5` | Passes L1–L5, fails at least one L6 task |
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
  --tasks TASK_ID [...]        Explicit subset of task IDs (default: all); mutually
                               exclusive with --task-group.
                               Choices: csv_nordic_property,
                                        python_safe_div, dotnet_sas, node_slugify,
                                        python_lru_cache, python_multifile_rename,
                                        node_csv_parser, python_lfu_cache,
                                        python_minheap, node_memoize_bug,
                                        python_ledger_bug, python_expr_eval,
                                        python_tokenizer, python_dijkstra,
                                        python_hashmap,
                                        node_debounce, python_merge_intervals,
                                        awk_csv_stats, java_word_freq,
                                        node_para_core, node_para_turret,
                                        node_para_entities, node_para_combat,
                                        node_paratrooper,
                                        context_8k, context_16k, context_32k,
                                        context_64k, context_128k, context_256k,
                                        multihop_forward, multihop_reverse,
                                        distractor_notes
  --task-group GROUP [...]     Task group shorthand; mutually exclusive with --tasks.
                               Can combine multiple groups.
                               Groups: coding (19 tasks), l6 (4 stepped tasks —
                                       node_para_core/turret/entities/combat),
                                       l6_full (1 task — node_paratrooper, full impl),
                                       context (6 tasks),
                                       multihop (3 tasks — multihop_forward,
                                       multihop_reverse, distractor_notes)
  --backend ollama|llama-server|vllm  Inference backend (default: ollama; env: BENCH_BACKEND)
  --model-file PATH            models/*.txt/.vllm file for GGUF/param lookup (required for
                               llama-server and vllm backends; compare.sh passes it automatically)
  --ollama-url URL             Default: http://localhost:11434 (ollama backend only)
  --num-ctx INT                Context window tokens (default: 8192); individual tasks
                               may specify a higher minimum via Task.num_ctx
  --temperature FLOAT          Default: 0.0
  --seed INT                   Default: 1
  --num-predict INT            Max output tokens (default: 400; compare.sh sets 8000 for
                               thinking models that exhaust token budgets during reasoning, and
                               verbose non-thinking models like gemma4:26b and gpt-oss:20b that
                               emit long preambles before BEGIN_FILE)
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
  --single-gpu INDEX           Run on a single CUDA device (index 0, 1, …). Strips
                               tensor_split from model params and sets
                               CUDA_VISIBLE_DEVICES=INDEX for the llama-server
                               subprocess. -1 = use all GPUs (default). Normally
                               controlled via gpu-mode.sh / .gpu-mode rather than
                               this flag directly.
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
./compare.sh --task-group coding
```

---

## vLLM backend

To benchmark using [vLLM](https://github.com/vllm-project/vllm)'s `vllm serve` instead of llama-server (recommended for dual-GPU tensor parallelism):

1. Install vLLM in the repo's `.venv`:
   ```bash
   ./install.sh   # section 7; or manually:
   .venv/bin/pip install vllm && .venv/bin/pip install 'gguf>=0.10.0'
   ```

2. Set `LLAMA_MODELS_DIR` to your GGUF directory:
   ```bash
   export LLAMA_MODELS_DIR=/path/to/gguf/models
   ```

3. Create or edit `models/default.vllm` (`.vllm` extension — auto-selected when `--backend vllm`):
   ```
   # short-name  gguf-file  params  hf:tokenizer-repo
   qwen2.5-coder:14b-vl  Qwen2.5-Coder-14B-Q4_K_M.gguf  tp=1,dtype=auto,max_model_len=32768  hf:Qwen/Qwen2.5-Coder-14B-Instruct
   llama3.3:70b-q4ks     Llama-3.3-70B-Q4_K_S.gguf       tp=2,dtype=auto,max_model_len=32768  hf:meta-llama/Llama-3.3-70B-Instruct
   ```
   The `hf:` field is required — it is passed as `--tokenizer` to vLLM for GGUF loading. For gated models (Llama 3.3), set `HF_TOKEN` or populate `hf-token.txt` in the repo root.

4. Run with the vLLM backend:
   ```bash
   ./compare.sh --backend vllm
   # or: BENCH_BACKEND=vllm ./compare.sh
   ```
   Output is written to `output/results-compare-vl.json`.

**Params field (`.vllm` files):**

| Param | vLLM CLI flag | Notes |
|-------|--------------|-------|
| `tp=N` | `--tensor-parallel-size N` | GPUs to use; `tp=2` for dual RTX 3090 |
| `dtype=auto` | `--dtype auto` | Let vLLM pick bf16/fp16 |
| `max_model_len=N` | `--max-model-len N` | Context cap; harness skips tasks requiring more (SKIPPED_CTX) |
| `gpu_mem_util=0.9` | `--gpu-memory-utilization 0.9` | Default is 0.9; lower if OOM |
| `enforce_eager` | `--enforce-eager` | Disables CUDA graphs; saves ~1 GB VRAM (critical for tight 24 GB budgets); ~20% slower inference |
| `thinking` | — | Harness-only; sets `"After your reasoning"` system prefix |

**Startup:** vLLM loads one model per `vllm serve` process. The harness starts it at the required context size and restarts automatically when the model changes or context grows. Startup is slower than llama-server (~400s for 32B on first launch including CUDA graph capture; `enforce_eager` skips graph capture).

**Timing:** `tok_per_s` uses wall time divided by `completion_tokens` (vLLM does not expose llama.cpp-style `timings` fields).

**Multi-GPU (tp=2):** Both GPUs must be visible and have equivalent VRAM. The harness does not set CUDA_VISIBLE_DEVICES — vLLM auto-detects all available GPUs and uses `tp` of them starting from GPU 0.

**Gated models:** `hf-token.txt` in the repo root is read automatically and forwarded as `HF_TOKEN` to the vLLM subprocess, so `meta-llama` models work without extra setup beyond populating that file.

**Single-GPU VRAM constraints (24 GB, 32B Q4_K_M):** Weights occupy ~20 GB, leaving only ~2.8 GB for KV cache. `enforce_eager` + `gpu_mem_util=0.94` squeezes this to `max_model_len=8192` (the practical ceiling — vLLM reports max 11 312 tokens; no coding task needs ctx between 8 192 and 16 384). Three tasks permanently SKIPPED: `csv_nordic_property` (16k), `python_multifile_rename` (16k), `python_expr_eval` (32k). **Thinking models** (deepseek-r1, qwq) additionally hit a 7 680-token output cap (`max_model_len − 512` prompt reserve), which exhausts the reasoning budget before `BEGIN_FILE` on L3+ tasks — those tasks pass on llama-server with larger context. Use `models/32gb.vllm` on a 32 GB card for full coverage.

**MoE GGUF models are not supported:** vLLM's `--load-format gguf` cannot map MoE expert weight tensors (`model.layers.X.mlp.experts.*`). All `*-A3B` / MoE GGUFs (qwen3-coder:30b, qwen3.5:35b, qwen3.6:35b, etc.) crash at startup with `Failed to map GGUF parameters`. Only dense models work via GGUF on vLLM. MoE models would require loading from HuggingFace safetensors (full bf16 weights, no GGUF), which is a separate setup. Use llama-server for MoE GGUF models.

**HF-format models (GPTQ/AWQ/safetensors):** The harness supports loading directly from a HuggingFace repo (no local GGUF needed) when the `gguf-file` field is omitted or set to `-` in the `.vllm` model file. vLLM downloads to `~/.cache/huggingface/hub/` on first run and auto-detects quantization from the repo's `config.json`. Example: `AxisQuant/Qwen3.6-27b-gptq-int4` runs as `vllm serve AxisQuant/Qwen3.6-27b-gptq-int4` (no `--load-format`, no `--tokenizer`). **Caveats:** some GPTQ repos use a `model_type` that vLLM maps to an SSM/Mamba-aware handler even for pure transformers, requiring `enforce_eager,max_num_seqs=1` to bypass CUDA graph Mamba-block allocation errors. GPTQ INT4 calibrated on generic text (C4) may also lose coding precision — `AxisQuant/Qwen3.6-27b-gptq-int4` scored 18/19 coding at 23 tok/s, worse than the bartowski Q4_K_M GGUF on llama-server (19/19, 36 tok/s) on both quality and speed.

**WSL2 `networkingMode=mirrored`:** Loopback connections go through Windows Firewall and may time out. The harness automatically falls back to the machine's LAN IP for inference calls (vLLM binds to `0.0.0.0`). Startup readiness is detected via log parsing rather than HTTP health checks, so both paths work regardless of network mode.

**Comparing all three backends:**
```bash
./compare.sh                        # → output/results-compare.json      (ollama)
./compare.sh --backend llama-server # → output/results-compare-ls.json   (llama-server)
./compare.sh --backend vllm         # → output/results-compare-vl.json   (vllm)
./compare-results.sh output/results-compare-ls.json output/results-compare-vl.json
```

---

## GPU mode (single vs. multi)

`gpu-mode.sh` lets you toggle between using all GPUs and a single GPU without editing model files.

```bash
./gpu-mode.sh               # show detected GPUs and current mode
./gpu-mode.sh toggle        # switch between single [GPU 0] and multi
./gpu-mode.sh single        # use GPU 0 only
./gpu-mode.sh single 1      # use GPU 1 only
./gpu-mode.sh multi         # use all GPUs (default)
```

The chosen mode is saved in `.gpu-mode` (gitignored). `run.sh` sources this file automatically, so the mode applies to every subsequent `./run.sh` and `./compare.sh` call without any extra flags.

**What changes in single-GPU mode:**

- `CUDA_VISIBLE_DEVICES=N` is exported — all backends (llama-server, vLLM, Ollama) inherit it.
- `tensor_split` is stripped from model params for llama-server (a multi-GPU split against a single-device server causes a startup error).
- Models in `models/*.txt` that list `tensor_split=1|1` will start normally on the chosen single GPU.

**Typical use cases:**

```bash
# Run candidates on 4090 only (avoids 3090 thermal load; all fit in 24 GB)
./gpu-mode.sh single 0
./run.sh --model-file models/candidates.txt --models noctrex-qwen3-coder:30b \
  --task-group coding --backend llama-server --num-predict 8000 --warmup

# Restore multi-GPU for 32B/70B models that need both cards
./gpu-mode.sh multi
./run.sh --model-file models/2x24gb.txt --models qwen2.5-coder:32b deepseek-r1:32b ...
```

> **Note:** vLLM with `tensor_parallel_size > 1` in the `.vllm` model file will fail when single-GPU mode is active — update `tp=1` in the model file for single-GPU vLLM runs.

---

## Hardware monitor (hwmonitor)

`run.sh` automatically starts `hwmonitor/hwmonitor.py` alongside every benchmark run. It watches GPU temperatures, power draw, and RAM — and aborts the benchmark cleanly if a critical threshold is breached (useful for long overnight runs where a fan failure could otherwise cook a card).

**What you see during a run:**

```
[hwmonitor] started — log: output/hwmonitor-20260619-143200.log
[i/1] qwen3-next:80b  python_safe_div ...
WARN      14:32:03  GPU1[3090] junction temp °C 93 ≥ 90
CRIT      14:32:05  GPU1[3090] junction temp °C 101 ≥ 100 — aborting bench.py PID 12345
          → SIGINT → PID 12345
          → PID 12345 exited after SIGINT
[hwmonitor] stopped
```

Data lines go to the log file only; WARN/CRIT/OK appear on stderr so they interleave naturally with bench.py progress output.

At the end of each run, `run.sh` prints the total elapsed wall time in `HH:MM:SS` format — useful for comparing run durations without a separate `time` command.

**Skip the watchdog for quick single-task runs:**

```bash
./run.sh --no-hwmonitor --models qwen3:14b --tasks python_safe_div
```

**Run standalone in a second terminal (more control):**

```bash
# Terminal 1 — monitor with custom thresholds
./hwmonitor/hwmonitor.py --warn-junction 88 --crit-junction 98

# Terminal 2 — run the benchmark
./run.sh --no-hwmonitor --model-file models/candidates.txt ...
```

**Default thresholds** (all overridable via CLI flags):

| Metric | WARN | CRIT |
|---|---|---|
| GPU core temp | 85 °C | 95 °C |
| GPU junction/hotspot | 90 °C | 100 °C |
| CPU package temp | 85 °C | 95 °C |
| GPU power (% of limit) | 98 % | — |
| RAM used | 90 % | — |

**Log file location:** `output/hwmonitor-<YYYYMMDD-HHMMSS>.log` — one file per run, written automatically.

See `hwmonitor/SPEC.md` for the full CLI reference and metric source table.

---

## Model files

Models are defined in `models/*.txt`. Each line has up to three fields:

```
<ollama-name>  [<gguf-file>  [<param>,<param>,...]]  [hf:<owner/repo>]
```

The `hf:` field is position-independent (may appear anywhere after the ollama name).

| File | Purpose |
|------|---------|
| `default.txt` | Canonical benchmark set — used by `./compare.sh` with no arguments |
| `experimental.txt` | Models under evaluation; not yet in the default set |
| `extended.txt` | Extended set for `./compare.sh extended` |
| `full.txt` | All tested models, including superseded ones |
| `24gb.txt` | Models confirmed to run well on a single 24 GB GPU |
| `32gb.txt` | Models requiring ~32 GB VRAM (e.g. 32B Q4_K_M + KV headroom) |
| `16gb.txt` | Models that fit on a 16 GB card |
| `2x24gb.txt` | Models for dual 24 GB GPUs (48 GB total); includes tensor_split=1|1 entries; use `gpu-mode.sh single` for models that fit in 24 GB |
| `3x24gb.txt` | Models for 3× 24 GB GPUs (72 GB total, PCIe); tensor_split=1|1|1; gpt-oss:120b and llama4-scout:17b GPU-resident at this tier |
| `4x24gb.txt` | Models for 4× 24 GB GPUs (96 GB total, PCIe); tensor_split=1|1|1|1; qwen3-next:80b context_256k architecture test; dense 32B at max_ctx=262144 |
| `2x32gb.txt` | Models needing dual 32 GB GPUs |

`.vllm` files mirror the GPU-tier `.txt` files but carry vLLM-specific params (`tp`, `enforce_eager`, `gpu_mem_util`):

| File | Purpose |
|------|---------|
| `default.vllm` | Canonical vLLM set — single-GPU 14B/32B entries + dual-GPU 70B entries |
| `32gb.vllm` | Single 32 GB GPU — 32B models at `max_model_len=32768` (unlocks all coding tasks) |
| `2x24gb.vllm` | Dual 24 GB GPUs (`tp=2`, 48 GB total) — standalone dual-GPU set including llama3.3:70b |
| `2x32gb.vllm` | Dual 32 GB GPUs (`tp=2`, 64 GB total) — 70B+ models at extended context |

Pass any file with `--model-file`:

```bash
BENCH_BACKEND=llama-server ./compare.sh --model-file models/experimental.txt
./run.sh --models mymodel:latest --model-file models/my-custom.txt
```

`compare.sh` with a named set (e.g. `./compare.sh extended`) auto-selects the corresponding file. Named sets: `default` → `default.txt`, `extended` → `extended.txt`.

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

### Discovering new models

`scout-hf.sh` periodically scans HuggingFace Hub across a curated set of queries covering the model families relevant to coding and context benchmarks (Qwen3-Coder, Qwen2.5-Coder, Devstral, DeepSeek-Coder, Llama3, Gemma, GPT-OSS, Codestral, Phi4). It saves a state snapshot after each run; subsequent runs diff against the snapshot and show only what changed — new repos, updated file lists (new quants added), and repos that disappeared.

```bash
# First run — shows the full list and saves state
./scout-hf.sh

# Subsequent runs — shows only new / updated / gone repos
./scout-hf.sh

# Dry-run without updating state
./scout-hf.sh --no-save

# Also print the full repo list on re-runs
./scout-hf.sh --show-all

# More repos per query (default: 8)
./scout-hf.sh --limit 12

# Override the default query list
./scout-hf.sh --queries "qwen3 coder" "llama4 instruct"
```

Each repo entry shows downloads, the recommended GGUF file, and a VRAM fit indicator: ✓ ≤20 GB (fits with KV headroom on a 24 GB card), `~` 20–24 GB (tight, limited KV cache), ✗ >24 GB (multi-GPU needed). State is saved to `output/hf-scout-state.json`.

---

## Exporting results

`statistics.sh` aggregates all `output/*.json` result files into a flat dataset for comparison across hardware or model versions. Results are sorted by `run_date` descending (newest first) by default.

```bash
# Default: one row per model, newest run first
./statistics.sh

# Context speed profile: pass% + tok/s for each context size (8k/32k/64k/128k/256k)
./statistics.sh --summary

# One row per task
./statistics.sh --detail --format csv --out stats.csv

# Sort by any column; optional direction asc or desc (default asc when column specified)
./statistics.sh --sort-by model
./statistics.sh --sort-by pass_pct desc
./statistics.sh --summary --sort-by ctx_128k desc

# JSON array for programmatic processing
./statistics.sh --format json --out stats.json

# Process a specific file only
./statistics.sh output/results-compare-ls.json --format markdown
```

### Cross-hardware sharing

Share results between machines so friends on different GPU tiers contribute real measurements to each other's VRAM estimation tables.

```bash
# On your machine — bundle all output/*.json into one sharable archive
./statistics.sh --export                          # → stats-exported.json (default)
./statistics.sh --export --out my-stats.json      # custom path

# On your friend's machine — extract the runs into their output/
./statistics.sh --import stats-exported.json

# Plain results file (not an export package) is also accepted
./statistics.sh --import output/results-compare-ls.json
```

Imported files land in `output/` in the native format under the name `results-import-<gpu_slug>-<instance_id>-<original_filename>.json`. Every machine gets a persistent 8-hex **instance ID** on first export (stored in `.instance-id`, gitignored). This means:

- **Two friends with the same GPU** (`RTX_3090_24GB`) never collide — different instance IDs produce different filenames and both coexist.
- **Re-importing from the same friend** (updated export) produces the same filenames and overwrites them — automatic update behaviour.

GPU slug examples:

| Hardware | Slug |
|---|---|
| RTX 3090 24 GB | `RTX_3090_24GB` |
| 2× RTX 3090 24 GB | `2x_RTX_3090_48GB` |
| RTX 3090 + RTX 4090 | `RTX_3090_RTX_4090_48GB` |
| AMD RX 7900 XTX | `RX_7900_XTX_24GB` |

Once imported, all `statistics.sh` commands pick up the foreign data automatically. For `--estimate-vram`, if the imported data comes from a different GPU tier, use `--anchor-vram N` to treat that tier as the estimation baseline:

```bash
# Friend has 2× RTX 3090 (48 GB total) — use their data as the 48 GB anchor
./statistics.sh --estimate-vram --anchor-vram 48
```

**Default mode** produces one row per `(model, backend)` with: hardware identifiers, pass rate, avg tok/s, total wall time, per-level skill breakdown (e.g. `L1:6/6  L2:4/5  L3:3/3`), error kind counts (`no_blocks`, `tests_still_fail`, `ctx_truncated`, `skipped_vram`, `skipped_ctx`, `slow`), and HF scout enrichment (`hf_downloads`, `hf_gguf_gb`) when `output/hf-scout-state.json` exists.

**Context summary mode** (`--summary`) produces one row per `(model, backend)` with: `vram_gb`, `pass_pct`, and a tok/s column per context size. Pass results show the generation tok/s; PASS_BUT_SLOW results append `~`; failures show a short code (`TRUNC`, `SKIP_VRAM`, `SKIP_CTX`, `T/O`, `FAIL`); tasks not run show `—`. The `ctx_256k` column is omitted automatically when no model ran that task.

**Detail mode** (`--detail`) produces one row per `(model, task)` with: all hardware fields, task difficulty, pass/fail, slow flag, error kind, tok/s, wall_s, prompt tokens, gen tokens, num_ctx, and truncation flags.

Hardware fields exported: GPU label (multi-GPU aware, e.g. `2× RTX 3090 24GB (48GB total)`), GPU count, total VRAM GB, compute capability, GPU driver, free VRAM at run start, GPU temperature, GPU power limit, CPU, RAM, platform, CUDA toolkit version, llama-server version (if applicable), Ollama version (if applicable), and storage device type.

The CSV format uses `;` as delimiter with all cells double-quoted (Nordic CSV — compatible with Excel on Nordic locales).

---

## Utility scripts

### fetch.sh — pull Ollama models

Pull one or more Ollama models by name or set:

```bash
./fetch.sh default              # pull all models in models/default.txt
./fetch.sh models/full.txt      # pull all models in a set file (by path)
./fetch.sh qwen2.5-coder:14b    # pull a single model
./fetch.sh default qwen3.5:7b   # mix: set + extra model
```

### powerlimit.sh — GPU power cap

Set or query the GPU power limit. On WSL2 (where `nvidia-smi` power management is blocked inside the VM) the script detects this and prints the exact PowerShell command to run in an elevated Windows terminal instead.

```bash
./powerlimit.sh             # set to $POWER_LIMIT env var, or 350 W default
./powerlimit.sh 300         # explicit wattage
./powerlimit.sh --query     # show current limits without changing anything
```

`compare.sh` calls this automatically at the start of each run. Export `POWER_LIMIT=<watts>` in your `.bashrc` to change the default.

### show-all-models.sh — inspect Ollama model details

Prints `ollama show` output for every model currently loaded in Ollama — useful for verifying quantization, parameter counts, and context window limits across your pulled models.

```bash
./show-all-models.sh
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

