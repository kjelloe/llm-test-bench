#!/usr/bin/env python3
"""CLI runner for the Ollama coding benchmark."""

import argparse
import shutil
import time
from pathlib import Path

from ollama_client import OllamaError, chat
from parsing import parse_file_blocks, validate_edits
from reporting import print_summary, write_results
from tasks import BUILTIN_TASKS, TASK_MAP, Task, build_prompt, prepare_workdir, run_setup, run_tests


def run_one(
    model: str,
    task: Task,
    ollama_url: str,
    num_ctx: int,
    temperature: float,
    seed: int,
    num_predict: int,
    keep_workdir: bool = False,
) -> dict:
    record: dict = {
        "model": model,
        "task": task.id,
        "baseline_failed": None,
        "baseline_rc": None,
        "edit_parse_ok": False,
        "edit_policy_ok": False,
        "tests_pass": False,
        "edited_files": [],
        "error_kind": None,
        "error_detail": None,
        "metrics": {},
        "tok_per_s": 0.0,
        "wall_s": 0.0,
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
        try:
            resp = chat(
                base_url=ollama_url,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                num_ctx=num_ctx,
                temperature=temperature,
                seed=seed,
                num_predict=num_predict,
            )
        except OllamaError as exc:
            record["error_kind"] = "TOOL_ERROR"
            record["error_detail"] = str(exc)[:500]
            return record

        m = resp.metrics
        record["metrics"] = {
            "prompt_eval_count": m.prompt_eval_count,
            "eval_count": m.eval_count,
            "prompt_eval_duration_ms": round(m.prompt_eval_duration / 1e6, 1),
            "eval_duration_ms": round(m.eval_duration / 1e6, 1),
            "total_duration_ms": round(m.total_duration / 1e6, 1),
        }
        record["tok_per_s"] = round(m.tok_per_s, 1)

        # --- parse edits ---
        edits = parse_file_blocks(resp.content)
        record["edit_parse_ok"] = bool(edits)
        if not edits:
            record["error_kind"] = "NO_BLOCKS"
            record["error_detail"] = resp.content[:300]
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
    parser = argparse.ArgumentParser(description="Benchmark local Ollama LLMs on coding tasks")
    parser.add_argument("--models", nargs="+", required=True, metavar="MODEL")
    parser.add_argument(
        "--tasks", nargs="+", default=None, metavar="TASK_ID",
        help=f"Subset of task IDs (default: all). Choices: {', '.join(TASK_MAP)}",
    )
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--num-predict", type=int, default=400)
    parser.add_argument("--out", default="results.json")
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

    pairs = [(m, tk) for m in args.models for tk in tasks_to_run]
    total = len(pairs)
    results = []

    for i, (model, task) in enumerate(pairs, 1):
        print(f"[{i}/{total}] model={model!r}  task={task.id!r} ...", end=" ", flush=True)
        record = run_one(
            model=model,
            task=task,
            ollama_url=args.ollama_url,
            num_ctx=args.num_ctx,
            temperature=args.temperature,
            seed=args.seed,
            num_predict=args.num_predict,
            keep_workdir=args.keep_workdirs,
        )
        status = "PASS" if record["tests_pass"] else f"FAIL({record.get('error_kind', '?')})"
        print(f"{status}  {record['wall_s']}s  {record['tok_per_s']} tok/s")
        results.append(record)

    write_results(results, args.out)
    print(f"\nResults written to {args.out}")
    print_summary(results)


if __name__ == "__main__":
    main()
