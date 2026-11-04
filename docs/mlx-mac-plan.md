# MLX backend: what has to happen on a Mac

Plan for `--backend mlx` (Apple Silicon, mlx-lm), from the first Mac tester's spec (M3 Pro, 36 GB unified memory,
2026-11-04). Step 1, the client for an already-running `mlx_lm.server`, is built and tested on Linux against a stand-in
server (`tests/test_mlx_client.py`, commit `b38bab8`). Everything below needs real Apple hardware, either to run or to
develop and test. Items that can be done from Linux are listed separately at the end.

## Two ways to run

| | A: all on the Mac | B: Mac infers, Linux grades |
|---|---|---|
| Mac runs | `mlx_lm.server` and the harness (`./run.sh`), task tests included | `mlx_lm.server` only |
| Linux runs | nothing | the harness, through `ssh -N -L 8085:127.0.0.1:8085 mac` |
| Mac needs | Python 3.12, Node 22, .NET 9 SDK, a JDK, mlx-lm | mlx-lm |
| Results | graded with macOS tools (BSD awk, no GNU `timeout`) | graded with the same tools as every other result here |
| `hardware.inference_host.same_machine_as_tests` | true | false |

A is what a tester can do alone; B is the one whose grading matches the rest of this repo's results. Start with A.

## Phase 2: validation on the Mac (the tester; no code changes expected)

Setup, once:
- Homebrew: `brew install python@3.12 node openjdk` (Node 18+ for `node --test`; `java_word_freq` needs `javac`), and
  the .NET 9 SDK from Microsoft's macOS installer (dotnet.microsoft.com; `dotnet_sas` targets net9.0).
- mlx-lm in its own venv, pinned: `python3.12 -m venv ~/mlx-env && ~/mlx-env/bin/pip install mlx-lm==0.32.2`.
- `git clone -b dev https://github.com/kjelloe/llm-test-bench && cd llm-test-bench`.
- `PYTHON=~/mlx-env/bin/python ./mlx-host-info.sh > mac.json`.

Checks, each with what it proves and what to send back:

| # | Run | Pass when | If not |
|---|---|---|---|
| V1 | smoke: `qwen2.5-coder:7b-mlx`, `--tasks python_safe_div` | PASS; `model_listed` true | the result JSON + server log |
| V2 | cache policy: V1 plus `python_lru_cache`, `--prompt-cache-size 0` on the server | `hardware.order_independent` true (every `cached_prompt_tokens` 0) | mlx-lm 0.32's cache cannot be turned off this way: we need another way (a server restart per task, or a later mlx-lm) |
| V3 | reasoning off: `qwen3.8:27b-mlx`, `--tasks python_safe_div`, no `--think` | no `reasoning_despite_off` in `backend_notes` | the template ignores `enable_thinking=false`: start the server with `--chat-template-args '{"enable_thinking":false}'` and repeat |
| V4 | output limit: V1 with `--num-predict 20` | `finish_reason` "length", `response_truncated` true | the result JSON |
| V5 | repeatability: the `spot` set twice in one order, once reversed (`--tasks` listed backwards) | the same `response_snippet` and `eval_count` per task in all three | which tasks differ (first divergent line) |
| V6 | coding group: `qwen3.8:27b-mlx`, `--task-group coding --num-predict 8000 --model-timeout 1200` | a score to compare with llama-server's 19/19 | infrastructure skips (SKIPPED_ENV, TOOL_ERROR) reported apart from model failures |
| V7 | memory headroom before anything larger: watch `memory_pressure` / Activity Monitor during V6 | pressure stays green, no swap | stop at the 27B; the 35B-A3B (20.4 GB) and long context need the headroom first |

Send back: every `output/*.json` from these runs, `mac.json`, the server's console output, and anything that looked
wrong. Known differences to expect in A: `awk_csv_stats` is graded by BSD awk (mawk on our Ubuntu), so a model using
non-POSIX awk can pass here and fail there or the reverse; speed shows 0 tok/s (mlx-lm reports no timings).

## Phase 3: development that needs a Mac (us, with a Mac to test on)

1. **Managed server** (`MLXManager`, the shape of `LlamaServerManager`): spawn `mlx_lm.server` on a free port, wait for
   `/health` = ok within a startup timeout, drain stderr into a ring buffer (the llama-server pipe lesson), report
   crashes (exit code + stderr tail, as `server_crash`), stop it on exit and on TOOL_ERROR, never touch a server it did
   not start. Per-run choice: external (`--mlx-url`, today) or managed (model file names the directory).
2. **A cache policy that is guaranteed**, if V2 shows `--prompt-cache-size 0` is not enough: restart per task, or
   whatever mlx-lm offers by then. Keep the per-record `cached_prompt_tokens` check either way.
3. **Memory on Apple Silicon**: the inference process's peak (mlx's `mx.get_peak_memory()` is only visible inside the
   server process, so either a small patch/plugin to report it or sampling the process RSS), system memory pressure
   (`memory_pressure`, `vm_stat`) before and after each task. Recorded as unified memory, never VRAM. Replaces the
   NVIDIA snapshots MLX records do not have.
4. **A Mac hardware watchdog** in hwmonitor's role: thermal state (`pmset -g therm`), memory pressure, swap; `sudo
   powermetrics` for power if the tester accepts sudo. Abort on CRIT as hwmonitor does.
5. **`run.sh` / `preflight.sh` on macOS**: run them under the stock bash 3.2 and BSD tools, fix what breaks
   (`preflight.sh` uses `mapfile` in its NVIDIA branch; `xargs -r`; the gamedev bash tasks need GNU `timeout`, i.e.
   `brew install coreutils` → `gtimeout`); preflight checks for mlx-lm, Node, .NET, javac on a Mac.
6. **Bigger models and context**: once V7 shows the headroom, `context_*` up to each model's `max_ctx`; never a rotating
   KV cache for a full-context comparison (mlx-lm 0.32's server has no such flag; check that a later version keeps it
   off).

## Can be done from Linux (no Mac needed)

- **Client-side timings**: request with `stream: true` and time the chunks — time to first token ≈ prefill, the rest
  over the following tokens ≈ decode — labelled `timing_source: client_stream` so it is never mistaken for
  llama-server's own timings. Testable against the stand-in server.
- `compare.sh` with a `.mlx` model set (one model per server today, so one run per model) and a backend suffix for its
  output names; `compare-results.sh` on MLX files.
- `configure.sh`: offer the MLX backend and write `BENCH_MLX_URL`.
- A short `how-to-mlx.md` once Phase 2 has settled the steps (the README section holds them until then).

## Decisions for us

- Results graded on the Mac (A) and on Linux (B) are kept apart in comparisons until V6 shows they agree.
- Whether Phase 3 item 1 is worth it depends on the tester: if runs stay manual, the external mode is enough.
