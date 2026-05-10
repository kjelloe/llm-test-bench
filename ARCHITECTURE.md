### Overview

This repo contains a local, reproducible benchmark harness for evaluating LLMs served by **Ollama** (running locally, typically in WSL) across three capability dimensions:

- **Coding (v1 — implemented):** fix broken code so deterministic tests pass.
- **Context & retrieval (v1 — implemented):** find information in long documents; profile tok/s collapse at different context sizes; multi-hop cross-reference retrieval across document positions.
- **Structured reasoning (v2 — planned):** structured Q&A across multiple documents with match-type grading.
- **Agent tasks (v3 — early design):** use tools to accomplish goals in a real environment.

All implemented tasks share the same harness (`bench.py`), protocol (`BEGIN_FILE/END_FILE` into `answer.txt`), and comparison table. This document covers the implemented architecture and the planned extensions.

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
requirements.txt          pytest + nvidia-ml-py (optional; bench runs without it)
install.sh                Interactive installer: checks and installs missing dependencies
run.sh                    Venv setup + bench.py entrypoint
compare.sh                Runs a model set (default/extended/full); reads models/*.txt; --num-predict 4800; forwards extra args
configure.sh              Prints current env variable state with set instructions; interactive wizard sets backend, URLs, paths, HF token, and runs the model optimizer (Step 7)
statistics.sh             Aggregates output/*.json into a flat dataset (markdown/CSV/JSON); thin wrapper for statistics.py
statistics.py             Dataset builder: one row per model (summary) or per task (--detail); exports hardware, pass rates, tok/s, skill breakdown
lib/optimize_models.py    Hardware-aware llama-server param optimizer: detects GPU/VRAM/compute, suggests ngl, split_mode, tensor_split, flash_attn, n_cpu_moe, KV cache type, batch sizes; writes back to models/*.txt; --suggest-ctx prints DEFAULT_CTX for configure.sh
preflight.sh              Dependency checker (GPU, Ollama, models, Python, Node, .NET)
fetch.sh                  Pulls models by set name, set file path, or bare model name
lib/                      Python support modules (imported by bench.py) and shell utilities
  tasks.py                Task dataclass, built-in task definitions, prompt builder, subprocess helpers
  ollama_client.py        POST /api/chat (non-streaming), metrics extraction; unload_model()
  llama_server_client.py  LlamaServerManager (spawn/restart/stop llama-server process) + chat() for OpenAI-compatible /v1/chat/completions; same interface as ollama_client
  model_config.py         Parses models/*.txt 3-field format (ollama-name gguf-file params) into ModelConfig dataclasses
  parsing.py              BEGIN_FILE/END_FILE parser, allow-list validation
  reporting.py            Comparison table (paginated), failure detail, JSON writer
  gpu_monitor.py          pynvml GPU telemetry: snapshots, peak poller, idle-wait with VRAM drain check
  hw_snapshot.py          Hardware snapshot: GPU list (nvidia-smi — name, VRAM, compute_cap, driver, thermal, power), CPU, RAM, platform, CUDA, Ollama/llama-server versions, storage type
  history.py              compare-history.json writer (cmd_save) and header printer (cmd_show)
  show-all-models.sh      Runs ollama show on every locally installed model
output/                   Runtime artifacts — git-ignored, created on first run
  results-compare.json    Written by compare.sh (default set)
  results-<set>.json      Written by compare.sh <set> (e.g. extended, full)
  results.json            Written by run.sh / bench.py --out default
  compare-history.json    Run summaries + per-model history archive
tests/
  conftest.py             sys.path shim
  test_parsing.py         Unit tests for the BEGIN_FILE/END_FILE parser
  test_model_config.py    Unit tests for the models/*.txt parser (ModelConfig, max_ctx, hf: field)
  test_harness_e2e.py     End-to-end harness self-test: mock chat_fn exercises run_one() pipeline (PASS / NO_BLOCKS / TESTS_STILL_FAIL / EDITED_NONEDITABLE_FILE) + comparison table render + skill-level logic; no Ollama or llama-server required
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
  python_tokenizer/       tokenizer.py (baseline), tests/test_tokenizer.py   — min_predict=12000  [state machine: ESCAPE→INIT bug; fix is ESCAPE→STRING]
  csv_nordic_property/    data.csv (5 000 rows × 103 cols, Nordic CSV), data_sample.csv (5-row sample for prompt), solution.py (skeleton), test_solution.py  — min_predict=12000  model_timeout=600  [code-gen from scratch: 10 data questions → answers.txt + quantile transform → output.csv]
  context_8k/             documents/incident_archive.txt (~5.5k tok, 100 records), answer.txt (baseline), tests/test_answer.py  — num_ctx=8192   [tok/s profiler]
  context_16k/            documents/incident_archive.txt (~11k tok, 200 records), answer.txt (baseline), tests/test_answer.py   — num_ctx=16384  [tok/s profiler]
  context_32k/            documents/incident_archive.txt (~22k tok, 400 records), answer.txt (baseline), tests/test_answer.py   — num_ctx=32768  [tok/s profiler]
  context_64k/            documents/incident_archive.txt (~44k tok, 800 records), answer.txt (baseline), tests/test_answer.py   — num_ctx=65536  [tok/s profiler]
  multihop_forward/       documents/incident_archive.txt (~30k tok, 400 records), answer.txt (baseline), tests/test_answer.py   — num_ctx=32768  [multi-hop: anchor @20%, answer @75%]
  multihop_reverse/       documents/incident_archive.txt (~30k tok, 400 records), answer.txt (baseline), tests/test_answer.py   — num_ctx=32768  [multi-hop: answer @20%, anchor @75%]
  distractor_notes/       documents/incident_archive.txt (~30k tok, 400 records), answer.txt (baseline), tests/test_answer.py   — num_ctx=32768  [distractor: 3 note-body cross-refs near true INCIDENT-5000 header @50%]
  context_128k/           documents/code_archive.py (~440 KB, ~110k tok Python stdlib), answer.txt (baseline), tests/test_answer.py  — num_ctx=131072  model_timeout=3600s
  context_256k/           documents/code_archive.py (~880 KB, ~220k tok Python stdlib), answer.txt (baseline), tests/test_answer.py  — num_ctx=262144  model_timeout=7200s  min_vram_gb=24

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
- Computes `total_vram_gb` from the hardware snapshot (`sum(gpu.vram_total_mb) / 1024`) once at startup; used for `SKIPPED_VRAM` pre-flight checks.
- Before each `run_one()` call, two pre-flight skip checks run: (1) **`SKIPPED_VRAM`** — if `task.min_vram_gb > 0` and `total_vram_gb < task.min_vram_gb`, a stub result is recorded and the task is skipped without calling the model; (2) **`SKIPPED_CTX`** (llama-server only) — if `cfg.max_ctx` is set and `effective_ctx > cfg.max_ctx`, a stub result is recorded and the task is skipped without restarting the server.
- Calls `run_one()` per pair; collects result records.
- On completion: writes results to `--out` path (default `output/results.json`) with hardware metadata included, prints the (paginated) comparison table, prints failure detail.
- Hardware snapshot (`hw_snapshot.get_hw_snapshot()`) is taken once at startup and attached to the results JSON and passed to `print_comparison_table` for display.

#### `tasks.py` — Task Library + Prompt Builder

Two responsibilities kept in one module to avoid a thin `prompting.py` abstraction:

- **`Task` dataclass**: `id`, `description`, `subdir`, `editable_files`, `context_files`, `test_cmd`, `test_timeout`, `setup_cmd`, `setup_timeout`, `difficulty` (1=L1/2=L2/3=L3/4=L4/5=L5, used for the Skill column), `num_ctx` (optional per-task context window override — runner uses `max(global, task.num_ctx)`), `min_predict` (optional per-task floor on `--num-predict`; useful when thinking models need extended token budget for reasoning before output), `model_timeout` (optional per-task override for the Ollama HTTP request timeout; context_128k and context_256k set 3600s/7200s respectively because prompt-eval alone at those sizes can exceed the default 300s), `min_vram_gb` (optional; if `total_vram_gb < min_vram_gb` the task is skipped before the model call with `SKIPPED_VRAM` — avoids multi-hour timeouts for tasks whose KV cache cannot fit on the hardware, e.g. `context_256k` sets `min_vram_gb=24`).
- **`build_prompt(task, workdir)`**: reads file contents and assembles the user message with `BEGIN_FILE/END_FILE` blocks for editable files and `--- path ---` fenced sections for context files.
- **`prepare_workdir`**, **`run_setup`**, **`run_tests`**: thin subprocess wrappers using `subprocess.run(..., timeout=...)`.
- **`BUILTIN_TASKS` / `TASK_MAP`**: the built-in task list and a lookup dict by task id.

#### `ollama_client.py` — Ollama Model Adapter

- `chat(...)` — main inference call. Uses `urllib.request` (stdlib); no third-party HTTP library. Accepts `think: bool` (reasoning tokens), `num_thread: int | None` (CPU cap), `keep_alive: str | int | None` (warmup calls use `-1` to keep model resident). Returns `OllamaResponse(content, thinking, metrics)`.
- `unload_model(base_url, model, timeout)` — POSTs to `/api/generate` with `keep_alive=0` to immediately evict model weights from VRAM. Fire-and-forget; exceptions swallowed. Called by `bench.py` before each model switch so the VRAM drain wait has something to wait for.
- Also exports `OllamaMetrics`, `OllamaResponse`, `OllamaError` — shared types re-used by `llama_server_client.py`.

#### `llama_server_client.py` — llama-server Backend Adapter

Provides the same `chat()` / `unload_model()` signatures as `ollama_client.py` so `bench.py` can select either backend at startup.

- **`LlamaServerManager`** — manages a single `llama-server` subprocess:
  - `ensure(cfg, ctx_size, num_threads, startup_timeout=600)` — starts or restarts the server if the model changed or `ctx_size` grew beyond the running instance. Blocks until `/health` returns `{"status":"ok"}` (up to `startup_timeout` seconds, default 600; large RAM-bound models with `mlock` may take 300–600s). If the server exits before becoming ready, its full stderr output is captured and included in the raised `RuntimeError` for diagnosis.
  - `stop()` — terminates the process; SIGTERM then SIGKILL on timeout; closes the stderr pipe.
  - Tracks `_current_model` and `_current_ctx` to minimise unnecessary restarts (never downsizes ctx — a server running at 131072 tokens is fine for an 8192-token task).
- **CTX_TRUNCATED recovery:** After any `CTX_TRUNCATED` result, `bench.py` calls `llama_manager.stop()` before the next task. This forces a clean server restart rather than leaving subsequent tasks to hang against an undersized context window.
- `chat(base_url, model, messages, ...)` — POST `/v1/chat/completions` (OpenAI-compatible). `model`, `num_ctx`, `num_thread`, `keep_alive`, `think` are ignored (llama-server is single-model per process; these are configured at startup). `tok_per_s` uses `timings.predicted_ms` from the llama.cpp response extension (generation phase only); falls back to `completion_tokens / wall_time` on older builds.
- `unload_model(...)` — no-op; lifecycle is managed by `LlamaServerManager.stop()`.

#### `model_config.py` — Model Config Parser

Parses the 3-field space-separated format used in `models/*.txt` files.

- **`ModelConfig`** dataclass: `ollama_name`, `gguf_file` (optional), `params` (dict: `str → str | bool`), `hf_repo` (optional), `max_ctx` (optional int — harness-only architecture limit, not forwarded to llama-server).
- `parse_model_line(line)` — parses one non-comment line; returns `None` for blank/comment lines.
- `load_model_file(path)` — returns a list of `ModelConfig` objects from a `models/*.txt` file.

Line format:
```
<ollama-name> [<gguf-file> [<key=val,flag,...>]]
```
Boolean params (e.g. `no_mmap`, `mlock`) become `True` in the dict. Key-value params (e.g. `n_cpu_moe=35`) store the string value. During server startup in `llama_server_client.py`, param names are mapped to CLI flags via `_PARAM_NAME_MAP` (e.g. `ngl` → `--n-gpu-layers`) before applying the generic underscore→hyphen rule; `|` in values is replaced with `,` (used by `tensor_split=1|1` to survive the comma-delimited params field: stored as `"1|1"`, emitted as `--tensor-split 1,1`). Boolean params listed in `_BOOL_EMIT_VALUE` emit `--flag value` instead of bare `--flag` — currently `flash_attn` → `--flash-attn on` (newer llama-server builds changed `--flash-attn` from a bare flag to an `on|off|auto` optional-value flag; bare `--flash-attn` would consume the next argument as its value and crash). `ngl` in model params controls GPU layer offload; the harness no longer injects a hardcoded `--n-gpu-layers` — models without `ngl` get llama-server's own default (full offload). `max_ctx=N` is parsed out and stored in `ModelConfig.max_ctx`; it is **not** added to `params` and is never forwarded to llama-server. It is used by `bench.py` to skip tasks whose `effective_ctx` exceeds the model's architecture limit, recording `SKIPPED_CTX`.

#### `gpu_monitor.py` — GPU Telemetry

Optional module; requires `nvidia-ml-py` (`pip install nvidia-ml-py`). Fails gracefully with a `RuntimeWarning` if pynvml is unavailable — all functions return `None` and the benchmark continues normally.

- `get_gpu_snapshot() -> dict | None` — single point-in-time sample: `vram_used_mb`, `gpu_util`, `mem_bandwidth_util` for GPU 0.
- `wait_for_gpu_idle(timeout, baseline_vram_mb, …) -> dict | None` — polls every 500ms until all three conditions hold simultaneously: `gpu_util < 5%`, `vram_used_mb < baseline_vram_mb + 200`, and VRAM delta < 50 MB between consecutive polls. Hard timeout: 10s. On timeout: returns last snapshot with `"dirty": True`; clean exit returns snapshot with `"dirty": False`. Used between model loads to ensure `before_load` captures true idle baseline.
- `launch_peak_poller(stop_event, poll_interval) -> (Thread, list)` — background thread that polls every 500ms until `stop_event` is set, then does one final poll. Records the sample with the highest `gpu_util` seen across all polls. Captures genuine peak GPU activity regardless of task duration (replaces the old fixed 5-second delayed snapshot which missed short tasks).

#### `parsing.py` — Edit Protocol Parser

- `parse_file_blocks(text)` — regex over `BEGIN_FILE <path>\n…\nEND_FILE`; returns `list[FileEdit]`.
- `validate_edits(edits, allow_list)` — returns violation strings for any path outside the allow-list.

#### `reporting.py` — Output

- `print_comparison_table(results, task_difficulties, model_timeout, hardware)` — paginated ASCII table: rows = models, columns = `Spd` + `Skill` + tasks + summary. When the full table would exceed the terminal width (detected via `shutil.get_terminal_size()`), tasks are split into pages printed as `[1/N]`, `[2/N]`, … with the full summary column repeated on each page. `Skill` shows the highest difficulty tier where the model passes all tasks at that level and below; `CTX_TRUNCATED`, `TOOL_ERROR`, `SKIPPED_CTX`, and `SKIPPED_VRAM` are excluded (infrastructure/hardware constraints, not capability gaps). `hardware` (optional dict from `hw_snapshot.get_hw_snapshot()`) is printed as a one-line summary under the table title.
- `print_summary(results)` — failure detail: error kind counts + one-line sample per category.
- `write_results(results, path, hardware)` — JSON dump; wraps results as `{"hardware": {...}, "results": [...]}` when hardware is provided.
- `load_results(path)` — reads both the old flat-list format and the new wrapped format; returns `(results, hardware)`.

#### `lib/hw_snapshot.py` — Hardware Snapshot

Captures a point-in-time hardware description at benchmark start:
- `get_hw_snapshot(llama_server_bin=None, models_dir=None) -> dict` — returns a dict with:
  - `gpu` — list of GPU dicts queried via `nvidia-smi` (two-pass: tries with `compute_cap` first, falls back without for older drivers): `name`, `vram_total_mb`, `vram_free_mb`, `driver`, `temp_c`, `power_draw_w`, `power_limit_w`, `clock_mhz`, `clock_max_mhz`, `compute_cap` (float, e.g. `12.0`; absent on older drivers)
  - `cpu` — model string + logical core count from `/proc/cpuinfo` (Linux) or `sysctl` (macOS)
  - `ram_total_gb` — total system RAM in GB
  - `platform` — `"Linux 6.6.87…"` etc.
  - `cuda_toolkit` — CUDA toolkit version from `nvcc --version` or version files; `""` if not found
  - `ollama_version` — from `ollama --version`; `""` if Ollama not installed
  - `llama_server_version` — from `llama-server --version`; only present when `llama_server_bin` is passed
  - `models_storage` — `{"device": str, "transport": str}` for the GGUF/Ollama model directory; transport is one of `nvme`, `ssd`, `hdd`, `windows-drive`, `network-or-virtual`, or a raw fs type
- `hw_summary(hw) -> str` — one-line string suitable for display, e.g. `RTX 5060 Ti 16GB  |  AMD Ryzen 7 5800X3D (16 logical cores)  |  64.0 GB RAM`.

The snapshot is saved in `results.json` as a top-level `"hardware"` field and in `compare-history.json` per run entry, allowing results from different machines or GPUs to be compared. For Ollama runs, `models_storage` auto-detects via `$OLLAMA_MODELS` or `~/.ollama/models`.

#### `lib/optimize_models.py` — Hardware-aware Model Optimizer

Called by `configure.sh` Step 7. Interactive CLI that reads current GPU/RAM state and suggests optimised llama-server startup params for each model in a `models/*.txt` file, then offers to write them back.

- Detects hardware via `nvidia-smi`: GPU count, per-GPU total and free VRAM, compute capability (Ampere/Ada/Blackwell). Falls back to name-based compute inference if `compute_cap` field is unsupported by the driver.
- Detects RAM via `/proc/meminfo`.
- For each model with a GGUF file: measures on-disk size (summing multi-part shards).
- Supports `--suggest-ctx` flag: prints the VRAM-tier recommended `DEFAULT_CTX` integer and exits (used by `configure.sh` to populate the export block without running the interactive optimizer).
- Key decision: **`full_gpu_fit`** = `gguf_gb ≤ total_vram × 0.85` (85% safety margin leaves headroom for KV cache, compute buffers, and display use). This flag drives most suggestions:

  | Condition | Action |
  |-----------|--------|
  | `full_gpu_fit` | `ngl=999`; remove `n_cpu_moe` (experts faster on GPU); remove `mlock`; `cache_type_k/v=f16` (max quality) |
  | `n_cpu_moe` set but not `full_gpu_fit` | `ngl=999` (dense layers to GPU, experts to CPU); `cache_type_k/v=q8_0` |
  | MoE model, no `n_cpu_moe`, not `full_gpu_fit` | add `n_cpu_moe=35` then `ngl=999`; `cache_type_k/v=q8_0` |
  | Large model not fitting any GPU | warn with estimated starting `ngl` value |
  | Model ≥ 8 GB and RAM ≥ 1.2× | `no_mmap` (benchmark timing: eager load, no page-fault variance; see SPEC) |
  | Model ≥ 16 GB, RAM-resident, RAM ≥ 1.5× | `mlock` (pin in RAM, prevent paging) |
  | GPU compute ≥ 8.0 (Ampere+) | `flash_attn` (emitted as `--flash-attn on`; faster attention, lower VRAM at long contexts) |
  | 2+ GPUs | `split_mode=row` (recommended default; `layer` may be faster for single-user PCIe token gen); `tensor_split=N|M` (weighted by free VRAM if GPUs differ by >1 GB, else `1|1`; `|` is sub-separator — CLI builder converts to `,`) |
  | All models | `batch_size` / `ubatch_size` tiered by total VRAM (16 GB: 512/128; 24 GB: 1024/256; 32 GB: 2048/512; 64 GB+: 4096/512) |
  | `turbo4`/`turbo3` cache type | replace with target KV type (`f16` or `q8_0`) |

- Prompts per model: apply / skip / apply-all / skip-all.
- Backs up the model file (`models/default.txt.bak`) before writing.
- Preserves `hf:` fields and inline comments when rewriting lines.

#### `lib/history.py` — Run History Manager

Called by `compare.sh` with two subcommands:
- `history.py show <stats_file> <model> ...` — prints the last-run summary and per-model history in the compare header.
- `history.py save <results_file> <stats_file>` — appends the current run to `output/compare-history.json`, keeping the last 10 runs.

#### `output/compare-history.json` — Run + Model Archive

Written by `compare.sh` (via `lib/history.py save`) after each run. Two top-level sections:

- **`runs`** — last 10 full run summaries (timestamp, models, tasks, overall pass/fail, per-model breakdown). Used by the `compare.sh` header to show estimated runtime for the next run.
- **`model_history`** — dict keyed by model name; each value is a list of that model's last 10 run entries (`timestamp`, `passes`, `total_tasks`, `avg_tok_per_s`, `total_wall_s`, `per_task`). Persists across model set changes — models swapped out of `bench-models.sh` retain their history and appear in the header as "Archived models".

### Data Model

Results are written as a JSON object `{"hardware": {...}, "results": [...]}`. The top-level `"hardware"` field contains the full snapshot from `hw_snapshot.get_hw_snapshot()` (gpu list with driver/thermal/power/compute_cap fields for each GPU, cpu string, ram_total_gb, platform, cuda_toolkit, ollama_version, llama_server_version, models_storage). Multiple GPUs are all recorded — `statistics.py` aggregates them into `gpu_count`, `total_vram_gb`, and a human-readable `gpu` label (e.g. `2× RTX 3090 24GB (48GB total)`). The old flat-list format is still readable via `load_results()`.

#### Result Record

| Field | Type | Notes |
|---|---|---|
| `model` | string | |
| `backend` | string | `"ollama"` or `"llama-server"` |
| `hf_repo` | string | HuggingFace repo (e.g. `bartowski/Qwen2.5-Coder-14B-Instruct-GGUF`); populated for llama-server runs when the model file includes an `hf:` field |
| `task` | string | |
| `baseline_failed` | bool | |
| `baseline_rc` | int | |
| `edit_parse_ok` | bool | |
| `edit_policy_ok` | bool | |
| `tests_pass` | bool | |
| `edited_files` | list[string] | |
| `error_kind` | string\|null | `NO_BLOCKS`, `CTX_TRUNCATED`, `EDITED_NONEDITABLE_FILE`, `TESTS_STILL_FAIL`, `BASELINE_PASSED_INVALID_TASK`, `TOOL_ERROR`, `SKIPPED_VRAM`, `SKIPPED_CTX` |
| `error_detail` | string\|null | truncated, max ~500 chars |
| `metrics` | object | `num_ctx`, `prompt_eval_count`, `eval_count`, `prompt_eval_duration_ms`, `eval_duration_ms`, `total_duration_ms` |
| `tok_per_s` | float | |
| `wall_s` | float | total including setup + model + tests |
| `response_truncated` | bool | true if `eval_count >= num_predict - 5` |
| `ctx_truncated` | bool | true if prompt was silently truncated (Ollama capped num_ctx below request); detected when `prompt_eval_count < len(prompt) // 5` |
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
- `CTX_TRUNCATED` if the prompt was silently truncated by Ollama (takes precedence over `NO_BLOCKS` when detected).
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
- Thinking models (gpt-oss:20b, gpt-oss:120b, gemma4:26b, qwen3.5:35b) consume generation tokens for reasoning before emitting `BEGIN_FILE`; `--num-predict 4800` is required for complex tasks (`compare.sh` sets this explicitly; 2400 was insufficient — gpt-oss:120b ran out mid-reasoning on CSV tasks and gemma4:26b/qwen3.5:35b failed basic tasks like `node_slugify` at 23–32 tok/s within ~100s). Per-task `min_predict` overrides handle tasks where reasoning alone can exceed the default budget — e.g. `python_dijkstra` (16000), `python_lfu_cache` (12000), `python_minheap` (12800), `python_expr_eval` (16000), `python_tokenizer` (12000), `python_hashmap` (16000), `node_slugify`/`node_csv_parser`/`python_lru_cache`/`node_memoize_bug` (8000 each), `csv_nordic_property` (12000), and `multihop_*` (12000) all carry elevated budgets because gpt-oss:20b burns thousands of reasoning tokens before emitting output. Note: gpt-oss:20b fails `multihop_forward` even at 12000 tokens — its thinking loop expands indefinitely when scanning forward through long documents, exhausting all budget. It similarly exhausts all budget on `python_tokenizer` (correctly identifies the ESCAPE→STRING fix but keeps reconsidering the buffer-handling line indefinitely). It also fails `distractor_notes` (correct answer requires reading the record header, not note-body mentions; gpt-oss:20b anchors on a later note-body occurrence with recency bias). All three are valid capability signals, not budget misconfigurations; gpt-oss:120b handles all correctly.
- Infrastructure failures are excluded from the `Skill` rating in the comparison table: `CTX_TRUNCATED`, `TOOL_ERROR`, `SKIPPED_CTX`, `SKIPPED_VRAM`. Only genuine capability failures (`TESTS_STILL_FAIL`, `NO_BLOCKS`, `EDITED_NONEDITABLE_FILE`) count against the skill score.
- `CTX_TRUNCATED` detection uses `prompt_eval_count < len(prompt) // 5` rather than `// 4`. The `// 4` threshold produced false positives on small code prompts (Python code tokenises at ~4.1 chars/token rather than 4.0, putting genuine full-context runs 24 tokens below the floor). The `// 5` floor still reliably catches real truncation events such as Ollama capping a 65k-token context request at 32768 tokens.
- Warmup is JIT per model: each model is warmed up immediately before its first task, not all at the start. Calls use `keep_alive=-1` so the model stays resident through all its tasks; memory-pressure eviction still applies.
- `--num-thread 10` caps CPU threads per inference request; negligible effect on GPU-bound models but reduces heat on the host CPU.
- GPU monitoring requires `nvidia-ml-py` and an NVIDIA GPU. Without it, `gpu_snapshots` and `kv_cache` fields are `null`; the benchmark otherwise runs identically.
- **llama-server backend**: requires `llama-server` binary on `PATH` and `LLAMA_MODELS_DIR` env var pointing to the directory containing GGUF files. Models without a GGUF filename in `models/*.txt` cannot be used and will error immediately. `--think` and `--warmup` are no-ops. `tok_per_s` is wall-time derived (less accurate than Ollama's internal `eval_duration`). Context window is set at server startup; the server restarts automatically when a task requires a larger `num_ctx` than the running instance (never downsizes — a larger-ctx instance serves smaller tasks too). `--num-thread` is passed as `--threads` at startup, not per-request.
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
