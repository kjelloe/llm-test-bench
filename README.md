# llm-test-bench

A local benchmark harness that answers one question: **which model, on my hardware, can actually
do the coding/reasoning task in front of me?**

Every model gets the same broken file and the same test suite. It must reply with corrected file
content in a strict `BEGIN_FILE / END_FILE` block — no prose, no markdown fences. Tests either pass
or they don't. There's no LLM-as-judge, no rubric, no vibes: pass/fail is deterministic (`temperature=0`,
fixed `seed`), and the harness measures tokens/second alongside correctness so you can see the
speed/quality tradeoff for your own GPU(s).

Runs against [Ollama](https://ollama.com), [llama.cpp](https://github.com/ggerganov/llama.cpp)'s
`llama-server`, or [vLLM](https://github.com/vllm-project/vllm) — same tasks, same scoring, so you
can compare backends on identical hardware.

---

## Why this exists

Public LLM leaderboards tell you how a model does on someone else's cloud GPUs against benchmarks
you can't inspect. This repo is for a different question: *given the GPU(s) actually in this box,
which locally-hosted model should I reach for right now* — for a quick bug fix, for a from-scratch
feature, for a 128k-token context question? The 39 tasks here are hand-written to isolate specific
failure modes (off-by-one bugs, precedence-swap bugs, silent wrong-output bugs, long-context needle
retrieval, multi-step data analysis) rather than to be gameable by memorization.

---

## Quick start

**Prerequisites:** Python 3.12+, Node.js 20+, .NET 9 SDK, and either Ollama or a local `llama-server`
binary. Run the interactive installer for anything missing:

```bash
./install.sh
./preflight.sh      # verify everything is wired up correctly
./configure.sh       # show detected GPU, Ollama models, env vars, and how to set them
```

**See what's available, then try one task without any model at all:**

```bash
# List every task: id, difficulty (L1-L6), group, one-line description
python3 bench.py --list-tasks

# Export a task as a standalone package (starting files + TASK.md + the exact
# prompt text) — hand it to any coding agent, human, or chat model to attempt
python3 bench.py --export-task python_hashmap --export-dir /tmp/hashmap-challenge
```

**Run a real benchmark:**

```bash
# One model, one task
./run.sh --models qwen2.5-coder:7b --tasks python_safe_div

# One model, the 19 coding tasks
./run.sh --models qwen2.5-coder:7b --task-group coding

# The canonical multi-model comparison (models/default.txt, all 39 tasks)
./compare.sh --backend llama-server
```

A comparison table prints at the end (see [Understanding the output](#understanding-the-output)),
and full results land in `output/*.json`.

---

## Everyday commands

```bash
# Run several models at once, custom output file
./run.sh --models qwen2.5-coder:7b gemma4:12b --out my-results.json

# Only a subset of tasks — combine groups freely
./compare.sh --task-group coding web
./run.sh --models <model> --task-group context multihop

# A named model set instead of default.txt
./compare.sh extended
BENCH_BACKEND=llama-server ./compare.sh --model-file models/experimental.txt

# 10-task spot check — the standard first-look at a new candidate model
./run.sh --models <model> --task-group spot --backend llama-server --model-file models/candidates.txt

# Debug a failure: keep the workdir so you can inspect/re-run tests by hand
./run.sh --models deepseek-r1:32b --tasks dotnet_sas --keep-workdirs
```

`--task-group` and `--tasks` are mutually exclusive. Task groups: `coding` (19), `web` (4), `l6` /
`para` (4 stepped Paratrooper steps), `l6_full` (1, the from-scratch Paratrooper implementation),
`context` (6), `multihop` (5), `spot` (10-task candidate-evaluation subset).

---

## Tasks

39 deterministic tasks across six difficulty tiers. Each is a realistic bug pattern — the model
sees only the broken file and the test suite, no hint about what's wrong.

| Group | Count | What it tests |
|---|---|---|
| **Coding** (`coding`) | 19 | Python, Node.js, .NET, Java, and AWK bugs, L1 (one-line fix) through L5 (multi-step algorithmic invariants like Dijkstra/hashmap tombstones) |
| **Web** (`web`) | 4 | FastAPI/Express endpoint bugs — validation, config loading, routing |
| **Paratrooper, stepped** (`l6`) | 4 | A 1982-arcade-game backend built up over 4 steps (7 → 40 cumulative tests); each step gets the reference implementation of all prior steps |
| **Paratrooper, full** (`l6_full`) | 1 | The same game, implemented from a spec with zero scaffolding — the hardest single task in the suite |
| **Context retrieval** (`context`) | 6 | Find a sentinel value in a Python-stdlib archive at 8k → 256k tokens; measures retrieval reliability and prompt-eval speed as context grows |
| **Multihop retrieval** (`multihop`) | 5 | Two-hop and five-hop reasoning across a synthetic incident/config archive; distractor-resistance test included |

Full per-task descriptions (exact bug, exact fix, why it's hard) are in [`SPEC.md`](SPEC.md) and in
each task's own `task_data/<id>/` directory. `--list-tasks` gives you the live, authoritative list —
trust it over any table here if they ever disagree.

### Skill and Peak ratings

The **Skill** column in every results table is the highest tier where a model passes *every* task at
that level and below:

| Rating | Meaning |
|---|---|
| `L6` | Passes everything, including the from-scratch Paratrooper task |
| `L5` | Passes L1–L5, fails at least one L6 task |
| `L4` – `L1` | Passes up through that tier, fails at least one task the tier above |
| `<L1` | Fails an L1 task |

`CTX_TRUNCATED` (server capped the context window due to insufficient VRAM/RAM) is excluded from
this calculation — a model isn't penalized in its skill tier for hardware it doesn't have.

---

## Understanding the output

```
COMPARISON TABLE [1/3]  (Spd: assumed rank 1=fastest  |  Skill: L1:6  L2:4  L3:5  L4:3  L5:2)
Hardware: RTX 4090 24GB + RTX 3090 24GB  |  AMD Ryzen 9 9900X (20 logical cores)  |  86.0 GB RAM
+--------------------+-----+-------+--------------------------+--  …  --+---------------------------+
| Model              | Spd | Skill | python_safe_div          |   …     | pass  avg tok/s   tot s   |
+--------------------+-----+-------+--------------------------+--  …  --+---------------------------+
| qwen3.8:27b        |  1  |  L6   | PASS    44.9t/s     7.1s |   …     | 19/19   44.9t/s    380s   |
| qwen2.5-coder:14b  |  3  |  L2   | PASS    83.0t/s     5.4s |   …     | 27/37   83.2t/s   1120s   |
+--------------------+-----+-------+--------------------------+--  …  --+---------------------------+

FAILURE DETAIL
  Model: qwen2.5-coder:14b
    TESTS_STILL_FAIL: 5
      e.g. python_hashmap — HashMap.delete() still uses direct slot-clear, not tombstone
```

Wide tables paginate automatically (`[1/3]`, `[2/3]`, …). Results also land in JSON — default
`output/results.json`, `output/results-compare.json` for `compare.sh`, `-ls`/`-vl` suffix per backend.

If `nvidia-ml-py` is installed (it is, via `requirements.txt`), each result record also carries GPU
telemetry: VRAM before/after model load, peak GPU utilization during generation, and KV-cache memory
delta per call — useful for comparing quantizations without guessing.

---

## Backends

| Backend | Flag | Best for |
|---|---|---|
| Ollama | default | Simplest setup; `ollama pull` and go |
| [llama-server](https://github.com/ggerganov/llama.cpp) | `--backend llama-server` | MoE-specific tuning (`n_cpu_moe`, KV cache dtype per model), multi-GPU `tensor_split`, the primary backend this repo's own findings are benchmarked on |
| [vLLM](https://github.com/vllm-project/vllm) | `--backend vllm` | Tensor-parallel multi-GPU, AWQ/GPTQ/FP8, continuous batching |

**llama-server** needs `LLAMA_MODELS_DIR` pointed at your GGUF directory and a `models/*.txt` entry
mapping each model name to a GGUF filename plus optional params:

```
# ollama-name        gguf-file                    key=val,flag,...
qwen2.5-coder:14b     qwen2.5-coder-14b-Q4_K_M.gguf
qwen3.6:27b           Qwen3.6-27B-Q4_K_M.gguf      ngl=999,cache_type_k=f16,cache_type_v=f16,flash_attn
```

```bash
./compare.sh --backend llama-server
# or: BENCH_BACKEND=llama-server ./compare.sh
```

**vLLM** needs a `models/*.vllm` file (`tp`, `dtype`, `max_model_len`, plus an `hf:` tokenizer repo
for GGUF loading):

```
qwen2.5-coder:14b-vl  Qwen2.5-Coder-14B-Q4_K_M.gguf  tp=1,dtype=auto,max_model_len=32768  hf:Qwen/Qwen2.5-Coder-14B-Instruct
```

```bash
./compare.sh --backend vllm
```

Both backends have significant edge cases (MoE GGUF loading, GPTQ/AWQ quirks, KV-cache dtype vs.
task-precision sensitivity, WSL2 networking) — see the **llama-server backend** and **vLLM backend**
sections in the repository's git history of this file, or ask; the authoritative, continuously-updated
notes now live in [`CLAUDE.md`](CLAUDE.md) (search "vLLM backend constraints") since that file is
what gets updated every time a new edge case is found.

**Downloading models:** `./search-hf.sh "qwen2.5 coder 14b"` finds candidates on HuggingFace Hub and
suggests a `models/*.txt` line; `./fetch-hf.sh` downloads every configured `hf:` entry (multi-shard
GGUFs are detected and assembled automatically). `./scout-hf.sh` periodically scans for new releases
and diffs against a saved state so re-runs only show what changed.

---

## Multi-GPU

`./gpu-mode.sh` toggles between single-GPU and all-GPUs without touching any model file:

```bash
./gpu-mode.sh single 0    # pin to GPU 0 — strips tensor_split, sets CUDA_VISIBLE_DEVICES
./gpu-mode.sh multi       # use every visible GPU (default)
```

`run.sh` sources the saved mode automatically. Model files carry a `tensor_split` param
(`tensor_split=1|1` for 2 GPUs, `1|1|1` for 3, etc.) that only takes effect in multi-GPU mode:

| File | VRAM tier |
|---|---|
| `8gb.txt` / `12gb.txt` / `16gb.txt` / `24gb.txt` | Single-GPU tiers |
| `32gb.txt` | Single 32 GB card |
| `2x24gb.txt` / `2x32gb.txt` | Dual-GPU tiers |
| `3x24gb.txt` / `4x24gb.txt` | 3- and 4-GPU tiers |
| `default.txt` | Canonical set for `./compare.sh` with no arguments |
| `extended.txt` | Larger comparison set for `./compare.sh extended` |
| `candidates.txt` | Models under active evaluation — pairs with `--task-group spot` |

`.vllm` files mirror the same tiers with vLLM-specific params (`tp`, `enforce_eager`, `gpu_mem_util`).

---

## Hardware monitor

`run.sh` starts `hwmonitor/hwmonitor.py` alongside every run automatically. It watches GPU/CPU temps,
power draw, and RAM, and aborts the benchmark (SIGINT → SIGTERM) if a critical threshold is breached
— useful for unattended overnight runs where a fan failure could otherwise damage a card.

```bash
./run.sh --no-hwmonitor ...                                    # skip it for a quick single-task run
./hwmonitor/hwmonitor.py --warn-junction 88 --crit-junction 98 # run standalone with custom thresholds
```

Default thresholds: GPU core 85°C/95°C (warn/crit), GPU junction 90°C/100°C, CPU package 85°C/95°C,
RAM 90% (warn only). Logs to `output/hwmonitor-<timestamp>.log`; see `hwmonitor/SPEC.md` for the full
reference.

---

## CLI reference

```bash
python3 bench.py --help
```

The essentials:

| Flag | Purpose |
|---|---|
| `--models MODEL [...]` | Required unless `--export-task` is given |
| `--export-task TASK_ID` / `--export-dir PATH` | Write a shareable task package and exit — no model needed |
| `--list-tasks` | Print every task id/difficulty/group/description and exit |
| `--tasks ID [...]` / `--task-group GROUP [...]` | Mutually exclusive; pick specific tasks or whole groups |
| `--backend {ollama,llama-server,vllm}` | Default `ollama`; env `BENCH_BACKEND` |
| `--model-file PATH` | Required for llama-server/vllm backends |
| `--num-ctx` / `--num-predict` | Context window / max output tokens (default 400; use 8000+ for thinking models) |
| `--temperature` / `--seed` | Default `0` / `1` — determinism by default |
| `--model-timeout` / `--startup-timeout` | Per-request timeout / server-boot timeout |
| `--single-gpu INDEX` | Pin to one GPU; normally set via `gpu-mode.sh` instead |
| `--set-power-limit WATTS` | Cap GPU power via `nvidia-smi` before the run |
| `--checkpoint-dir PATH` | Resume a multi-model run per-model after an interruption |
| `--debug` | Stream server subprocess output live (llama-server/vllm) |
| `--keep-workdirs` | Don't delete temp workdirs — for post-mortem debugging |
| `--out FILE` | Results JSON path (default `output/results.json`) |

`run.sh` and `compare.sh` forward any extra flags straight to `bench.py`:

```bash
./compare.sh --num-ctx 16384 --num-predict 500
./run.sh --models qwen2.5-coder:14b --tasks node_slugify python_safe_div
```

---

## What can these models actually do?

Results change every time a new model, quant, or llama-server build lands — a static table here
goes stale fast (an earlier version of this README claimed a specific task had "never been passed
by any model"; that stopped being true weeks later). The living answer lives in two places:

- **[`CLAUDE.md`](CLAUDE.md)** — continuously-updated per-model findings: exact pass/fail per task,
  root-cause notes for every failure mode, speed at every context depth, config sensitivities.
  This is the source of truth; check it before trusting any number written down elsewhere.
- **`reports/`** — periodic full-fleet snapshot reports (`models-status-<Month>-<Year>.md`), each
  one a point-in-time cross-model comparison suitable for sharing outside this repo.

As a taste of what's achievable on this hardware class as of writing: several models now clear
**every task in the suite** (19/19 coding + 4/4 web + all 5 Paratrooper stages including the
from-scratch implementation) on a single 24 GB GPU or a 2–3 GPU rig. See `CLAUDE.md` for which ones,
and for the VRAM tier that fits your setup.

---

## Adding a task

1. Create `task_data/<your_task>/` with the baseline (broken) source file(s) and a test suite.
2. Confirm the baseline **fails**: `pytest` / `node --test` / `dotnet test` exits non-zero unmodified.
3. Add a `Task(...)` entry in `lib/tasks.py` and register it in `BUILTIN_TASKS`.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for a complete worked example, including how the editable-
files allow-list and context-files list are used to build the model-facing prompt.

---

## Further reading

| Doc | Covers |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Working agreement + the continuously-updated per-model findings log (the real source of truth for "does model X pass task Y") |
| [`SPEC.md`](SPEC.md) | Product spec — task authoring contract, result record schema, full per-task functional requirements |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Module-by-module internals: `tasks.py`, the backend clients, the parser/validator, reporting |
| `hwmonitor/SPEC.md` | Hardware watchdog CLI reference and metric sources |

Run the harness's own unit tests with `python3 -m pytest tests/ -v`.
