#!/usr/bin/env python3
"""CLI runner for the Ollama / llama-server coding benchmark."""

import argparse
import os
import shutil
import threading
import time
from pathlib import Path

from lib.gpu_monitor import get_gpu_snapshot, launch_peak_poller, wait_for_gpu_idle
from lib.hw_snapshot import get_hw_snapshot
from lib.ollama_client import OllamaError
from lib.parsing import parse_file_blocks, validate_edits
from lib.reporting import print_comparison_table, print_summary, write_results
from lib.tasks import BUILTIN_TASKS, TASK_MAP, Task, build_prompt, prepare_workdir, run_setup, run_tests


def _no_blocks_detail(resp, num_predict: int) -> str:
    """Build a diagnostic string for NO_BLOCKS failures."""
    truncated = resp.metrics.eval_count >= num_predict - 5
    parts = []
    if resp.thinking:
        parts.append(f"[thinking: {resp.thinking[:120].replace(chr(10), ' ')}…]")
    raw = resp.content
    if raw:
        snippet = raw[:200] if len(raw) <= 200 else raw[:100] + "\n…\n" + raw[-100:]
        parts.append(snippet)
    if truncated and not raw:
        parts.append(f"[response empty — all {resp.metrics.eval_count} tokens used for thinking]")
    return "\n".join(parts) if parts else "(empty response)"


def run_one(
    model: str,
    task: Task,
    client_url: str,
    num_ctx: int,
    temperature: float,
    seed: int,
    num_predict: int,
    model_timeout: int,
    chat_fn,
    think: bool = False,
    keep_workdir: bool = False,
    num_thread: int | None = None,
    gpu_before: dict | None = None,
    gpu_after: dict | None = None,
    backend: str = "ollama",
) -> dict:
    record: dict = {
        "model": model,
        "backend": backend,
        "task": task.id,
        "baseline_failed": None,
        "baseline_rc": None,
        "edit_parse_ok": False,
        "edit_policy_ok": False,
        "tests_pass": False,
        "response_truncated": False,
        "ctx_truncated": False,
        "response_snippet": None,
        "edited_files": [],
        "error_kind": None,
        "error_detail": None,
        "metrics": {},
        "tok_per_s": 0.0,
        "wall_s": 0.0,
        "kv_cache": None,
    }
    wall_start = time.monotonic()
    workdir = prepare_workdir(task)
    try:
        # --- setup ---
        if task.setup_cmd:
            ok, out = run_setup(task, workdir)
            if not ok:
                record["error_kind"] = "TOOL_ERROR"
                record["error_detail"] = f"setup failed: {out}"
                return record

        # --- baseline verification ---
        baseline_pass, baseline_out = run_tests(task, workdir)
        record["baseline_rc"] = 0 if baseline_pass else 1
        record["baseline_failed"] = not baseline_pass
        if baseline_pass:
            record["error_kind"] = "BASELINE_PASSED_INVALID_TASK"
            record["error_detail"] = baseline_out
            return record

        # --- model call ---
        prompt = build_prompt(task, workdir)
        effective_num_ctx = max(num_ctx, task.num_ctx) if task.num_ctx else num_ctx
        effective_num_predict = max(num_predict, task.min_predict) if task.min_predict else num_predict
        effective_timeout = task.model_timeout if task.model_timeout else model_timeout
        vram_pre = get_gpu_snapshot()   # before prompt eval — weights loaded, no KV cache yet
        stop_poll = threading.Event()
        poll_thread, snap_holder = launch_peak_poller(stop_poll)
        try:
            resp = chat_fn(
                base_url=client_url,
                model=model,
                messages=[
                    {"role": "system", "content": "Output ONLY BEGIN_FILE/END_FILE blocks. No markdown, no prose, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                num_ctx=effective_num_ctx,
                temperature=temperature,
                seed=seed,
                num_predict=effective_num_predict,
                timeout=effective_timeout,
                think=think,
                num_thread=num_thread,
            )
        except OllamaError as exc:
            stop_poll.set()
            poll_thread.join(timeout=2.0)
            err_str = str(exc)
            # llama-server returns HTTP 400 with "exceed_context_size_error" when the
            # server silently capped --ctx-size below our request (e.g. VRAM limit).
            # Treat this the same as Ollama's silent ctx downgrade.
            if "exceed_context_size_error" in err_str or "exceeds the available context size" in err_str:
                record["error_kind"] = "CTX_TRUNCATED"
            else:
                record["error_kind"] = "TOOL_ERROR"
            record["error_detail"] = err_str[:500]
            record["gpu_snapshots"] = {"before_load": gpu_before, "after_load": gpu_after, "peak_during_gen": None}
            return record
        vram_post = get_gpu_snapshot()  # after full inference — weights + KV cache (prompt + output)
        stop_poll.set()
        poll_thread.join(timeout=2.0)
        peak_snap = snap_holder[0] if snap_holder else None
        record["gpu_snapshots"] = {
            "before_load": gpu_before,
            "after_load": gpu_after,
            "peak_during_gen": peak_snap,
        }

        m = resp.metrics
        record["metrics"] = {
            "num_ctx": effective_num_ctx,
            "prompt_eval_count": m.prompt_eval_count,
            "eval_count": m.eval_count,
            "prompt_eval_duration_ms": round(m.prompt_eval_duration / 1e6, 1),
            "eval_duration_ms": round(m.eval_duration / 1e6, 1),
            "total_duration_ms": round(m.total_duration / 1e6, 1),
        }
        record["tok_per_s"] = round(m.tok_per_s, 1)
        # Detect silent num_ctx downgrade: Ollama may cap the context below our request
        # when VRAM is insufficient. Actual chars/token for this workload is ~3-4, so
        # len(prompt)//5 is a conservative floor. Using //4 caused false positives on
        # small code prompts where the actual ratio is ~4.1 chars/token.
        record["ctx_truncated"] = m.prompt_eval_count < len(prompt) // 5

        total_kv_tokens = m.prompt_eval_count + m.eval_count
        kv_delta_mb: int | None = None
        kv_mb_per_1k: float | None = None
        if vram_pre and vram_post and total_kv_tokens > 0:
            kv_delta_mb = max(0, vram_post["vram_used_mb"] - vram_pre["vram_used_mb"])
            if kv_delta_mb > 0:
                kv_mb_per_1k = round(kv_delta_mb / total_kv_tokens * 1000, 1)
        record["kv_cache"] = {
            "vram_before_mb": vram_pre["vram_used_mb"] if vram_pre else None,
            "vram_after_mb": vram_post["vram_used_mb"] if vram_post else None,
            "delta_mb": kv_delta_mb,
            "prompt_tokens": m.prompt_eval_count,
            "gen_tokens": m.eval_count,
            "total_tokens": total_kv_tokens,
            "kv_mb_per_1k_tokens": kv_mb_per_1k,
        }
        record["response_truncated"] = m.eval_count >= effective_num_predict - 5
        # Save a snippet of the raw model output for post-hoc debugging
        raw = resp.content
        record["response_snippet"] = (raw[:300] if len(raw) <= 300 else raw[:150] + "\n…\n" + raw[-150:])

        # --- parse edits ---
        edits = parse_file_blocks(resp.content)
        record["edit_parse_ok"] = bool(edits)
        if not edits:
            record["error_kind"] = "CTX_TRUNCATED" if record["ctx_truncated"] else "NO_BLOCKS"
            record["error_detail"] = _no_blocks_detail(resp, effective_num_predict)
            return record

        # --- policy check ---
        violations = validate_edits(edits, task.editable_files)
        record["edit_policy_ok"] = not violations
        if violations:
            record["error_kind"] = "EDITED_NONEDITABLE_FILE"
            record["error_detail"] = "; ".join(violations)[:500]
            return record

        # --- apply edits ---
        for edit in edits:
            target = workdir / edit.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(edit.content, encoding="utf-8")
        record["edited_files"] = [e.path for e in edits]

        # --- post-edit tests ---
        passed, out = run_tests(task, workdir)
        record["tests_pass"] = passed
        if not passed:
            record["error_kind"] = "TESTS_STILL_FAIL"
            record["error_detail"] = out

    finally:
        record["wall_s"] = round(time.monotonic() - wall_start, 2)
        if keep_workdir:
            print(f"  workdir kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local LLMs on coding tasks (Ollama or llama-server)")
    parser.add_argument("--models", nargs="+", required=True, metavar="MODEL")
    parser.add_argument(
        "--tasks", nargs="+", default=None, metavar="TASK_ID",
        help=f"Subset of task IDs (default: all). Choices: {', '.join(TASK_MAP)}",
    )
    parser.add_argument(
        "--backend", default=os.environ.get("BENCH_BACKEND", "ollama"),
        choices=["ollama", "llama-server"],
        help="Inference backend (default: ollama; env: BENCH_BACKEND)",
    )
    parser.add_argument(
        "--model-file", default=None, metavar="PATH",
        help="models/*.txt file for GGUF/param lookup (required for --backend llama-server)",
    )
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--num-predict", type=int, default=400,
                        help="Max tokens to generate. Use 1200+ for thinking models (default: 400)")
    parser.add_argument("--model-timeout", type=int, default=300,
                        help="HTTP request timeout in seconds (default: 300)")
    parser.add_argument("--startup-timeout", type=int, default=600,
                        help="Seconds to wait for llama-server to become ready (default: 600; large mlock models may need 300+)")
    parser.add_argument("--num-thread", type=int, default=10,
                        help="CPU threads for inference; 0 = let backend decide (default: 10)")
    parser.add_argument("--think", action="store_true", default=False,
                        help="Enable thinking/reasoning mode (ollama only; default: off)")
    parser.add_argument("--warmup", action="store_true", default=False,
                        help="Warm up each model before its first task (ollama only; default: off)")
    parser.add_argument("--out", default="output/results.json")
    parser.add_argument("--keep-workdirs", action="store_true",
                        help="Do not delete temp workdirs (useful for debugging)")
    args = parser.parse_args()

    if args.tasks:
        unknown = [t for t in args.tasks if t not in TASK_MAP]
        if unknown:
            parser.error(f"Unknown task IDs: {unknown}. Available: {sorted(TASK_MAP)}")
        tasks_to_run = [TASK_MAP[t] for t in args.tasks]
    else:
        tasks_to_run = BUILTIN_TASKS

    # ── Backend setup ─────────────────────────────────────────────────────────
    num_thread_opt = args.num_thread if args.num_thread > 0 else None
    llama_manager = None
    model_configs: dict = {}

    if args.backend == "llama-server":
        import shutil
        from lib.llama_server_client import LlamaServerManager
        from lib.llama_server_client import chat as _chat_fn
        from lib.llama_server_client import unload_model as _unload_fn
        from lib.model_config import load_model_file

        models_dir = os.environ.get("LLAMA_MODELS_DIR", "")
        if not models_dir:
            parser.error("LLAMA_MODELS_DIR environment variable must be set for --backend llama-server")
        if not args.model_file:
            parser.error("--model-file is required for --backend llama-server")

        bin_path = os.environ.get("LLAMA_SERVER_BIN") or shutil.which("llama-server") or ""
        if not bin_path:
            parser.error(
                "llama-server binary not found on PATH.\n"
                "  Install llama.cpp:  https://github.com/ggerganov/llama.cpp/releases\n"
                "  Or point to the binary:  export LLAMA_SERVER_BIN=/path/to/llama-server"
            )

        cfgs = load_model_file(args.model_file)
        model_configs = {c.ollama_name: c for c in cfgs}
        llama_manager = LlamaServerManager(models_dir=models_dir, bin_path=bin_path)
    else:
        from lib.ollama_client import chat as _chat_fn
        from lib.ollama_client import unload_model as _unload_fn

    hw = get_hw_snapshot()
    pairs = [(m, tk) for m in args.models for tk in tasks_to_run]
    total = len(pairs)
    results = []
    current_model: str | None = None
    current_ctx: int = 0
    gpu_before: dict | None = None
    gpu_after: dict | None = None

    startup_snap = get_gpu_snapshot()
    system_baseline_vram_mb: int | None = startup_snap["vram_used_mb"] if startup_snap else None

    task_difficulties = {t.id: t.difficulty for t in tasks_to_run}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    try:
        for i, (model, task) in enumerate(pairs, 1):
            effective_ctx = max(args.num_ctx, task.num_ctx) if task.num_ctx else args.num_ctx

            if llama_manager is not None:
                # llama-server: restart when model changes or ctx grows
                cfg = model_configs.get(model)
                if cfg is None:
                    parser.error(f"Model {model!r} not found in {args.model_file}")
                if llama_manager.needs_restart(cfg, effective_ctx):
                    if llama_manager._current_model is not None:
                        print(f"  [llama-server] stopping {llama_manager._current_model!r} ...",
                              end=" ", flush=True)
                        llama_manager.stop()
                        print("done")
                    gpu_before = wait_for_gpu_idle(baseline_vram_mb=system_baseline_vram_mb)
                    if gpu_before and gpu_before.get("dirty"):
                        print(
                            f"  [gpu] WARNING: VRAM ({gpu_before['vram_used_mb']} MB) did not drain to "
                            f"baseline ({system_baseline_vram_mb} MB + 200) within 10s — "
                            f"before_load snapshot is dirty"
                        )
                    print(f"  [llama-server] starting {model!r} ctx={effective_ctx} ...",
                          end=" ", flush=True)
                    t0 = time.monotonic()
                    llama_manager.ensure(cfg, effective_ctx, num_threads=num_thread_opt,
                                         startup_timeout=args.startup_timeout)
                    print(f"done  {time.monotonic() - t0:.1f}s")
                    gpu_after = get_gpu_snapshot()
                    current_model = model
                    current_ctx = effective_ctx
                client_url = llama_manager.base_url

            else:
                # Ollama: restart on model switch only
                if model != current_model:
                    if current_model is not None:
                        print(f"  [gpu] unloading {current_model!r} ...", end=" ", flush=True)
                        _unload_fn(args.ollama_url, current_model)
                        print("done")
                    gpu_before = wait_for_gpu_idle(baseline_vram_mb=system_baseline_vram_mb)
                    if gpu_before and gpu_before.get("dirty"):
                        print(
                            f"  [gpu] WARNING: VRAM ({gpu_before['vram_used_mb']} MB) did not drain to "
                            f"baseline ({system_baseline_vram_mb} MB + 200) within 10s — "
                            f"before_load snapshot is dirty"
                        )
                    gpu_after = None
                    if args.warmup:
                        print(f"  [warmup] {model!r} ...", end=" ", flush=True)
                        t0 = time.monotonic()
                        try:
                            _chat_fn(
                                base_url=args.ollama_url,
                                model=model,
                                messages=[{"role": "user", "content": "Say OK."}],
                                num_ctx=512,
                                temperature=0.0,
                                seed=1,
                                num_predict=5,
                                timeout=args.model_timeout,
                                think=False,
                                num_thread=num_thread_opt,
                                keep_alive=-1,
                            )
                            print(f"done  {time.monotonic() - t0:.1f}s")
                        except Exception as exc:
                            print(f"FAILED ({exc})")
                        gpu_after = get_gpu_snapshot()
                    current_model = model
                client_url = args.ollama_url

            print(f"[{i}/{total}] model={model!r}  task={task.id!r} ...", end=" ", flush=True)
            record = run_one(
                model=model,
                task=task,
                client_url=client_url,
                num_ctx=args.num_ctx,
                temperature=args.temperature,
                seed=args.seed,
                num_predict=args.num_predict,
                model_timeout=args.model_timeout,
                chat_fn=_chat_fn,
                think=args.think,
                keep_workdir=args.keep_workdirs,
                num_thread=num_thread_opt,
                gpu_before=gpu_before,
                gpu_after=gpu_after,
                backend=args.backend,
            )
            if llama_manager is not None:
                cfg = model_configs.get(model)
                if cfg and cfg.hf_repo:
                    record["hf_repo"] = cfg.hf_repo

            status = "PASS" if record["tests_pass"] else f"FAIL({record.get('error_kind', '?')})"
            trunc = " TRUNCATED" if record.get("response_truncated") else ""
            print(f"{status}{trunc}  {record['wall_s']}s  {record['tok_per_s']} tok/s")
            results.append(record)

            # llama-server silently caps ctx when VRAM is insufficient; subsequent
            # requests against the same server process hang or error. Force a clean
            # restart before the next task so needs_restart() picks it up.
            if record.get("error_kind") == "CTX_TRUNCATED" and llama_manager is not None:
                print("  [llama-server] CTX_TRUNCATED — stopping server for fresh restart on next task",
                      flush=True)
                llama_manager.stop()

    finally:
        if llama_manager is not None:
            llama_manager.stop()
        if results:
            write_results(results, args.out, hardware=hw)
            print(f"\nResults written to {args.out}")
            print_comparison_table(results, task_difficulties=task_difficulties, model_timeout=args.model_timeout, hardware=hw)
            print_summary(results)


if __name__ == "__main__":
    main()
