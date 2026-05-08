import json
import shutil
from collections import defaultdict
from pathlib import Path


def _backend_suffix(backend: str) -> str:
    return "ls" if backend == "llama-server" else backend


def _make_display_key_fn(results: list[dict]):
    """Return a function r → display_key that appends [backend] only when needed."""
    backends_by_model: dict[str, set[str]] = defaultdict(set)
    for r in results:
        backends_by_model[r["model"]].add(r.get("backend", "ollama"))
    multi = {m for m, bs in backends_by_model.items() if len(bs) > 1}

    def display_key(r: dict) -> str:
        m = r["model"]
        if m not in multi:
            return m
        return f"{m} [{_backend_suffix(r.get('backend', 'ollama'))}]"

    return display_key


def write_results(results: list[dict], path: str, hardware: dict | None = None) -> None:
    payload: list | dict = (
        {"hardware": hardware, "results": results} if hardware else results
    )
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_results(path: str) -> tuple[list[dict], dict | None]:
    """Load a results file, handling both the old flat-list and new {hardware, results} formats."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, None
    return data["results"], data.get("hardware")


def _skill_level(model: str, tasks: list[str], idx: dict, task_difficulties: dict[str, int]) -> str:
    """Return highest difficulty tier N where the model passes ALL tasks at levels 1..N.

    CTX_TRUNCATED failures are hardware constraints (insufficient VRAM/RAM), not capability
    failures — they are excluded from the skill calculation.
    """
    if not task_difficulties:
        return "?"
    max_level = max(task_difficulties.get(t, 1) for t in tasks)
    for level in range(max_level, 0, -1):
        tasks_up_to = [t for t in tasks if task_difficulties.get(t, 1) <= level]
        def _counts_as_pass(model: str, t: str) -> bool:
            r = idx.get((model, t), {})
            if r.get("tests_pass"):
                return True
            if r.get("error_kind") == "CTX_TRUNCATED":
                return True  # hardware limit, not a capability gap
            return False
        if all(_counts_as_pass(model, t) for t in tasks_up_to):
            return f"L{level}"
    return "<L1"


def print_comparison_table(results: list[dict], task_difficulties: dict[str, int] | None = None, model_timeout: int | None = None, hardware: dict | None = None) -> None:
    dk = _make_display_key_fn(results)
    models = list(dict.fromkeys(dk(r) for r in results))
    tasks  = list(dict.fromkeys(r["task"] for r in results))
    idx    = {(dk(r), r["task"]): r for r in results}

    speed_rank = {m: i + 1 for i, m in enumerate(models)}

    model_w = max(len("Model"), max(len(m) for m in models))
    CELL_W  = 24   # "PASS  1234.5t/s    14.2s"
    SUM_W   = 25   # "3/3  1234.5t/s  1234.5s"
    SPD_W   = 3
    SKILL_W = 5

    # Fixed columns overhead: "| model | Spd | Skill " prefix + "| summary |" suffix
    FIXED_W = (model_w + 3) + (SPD_W + 3) + (SKILL_W + 3) + (SUM_W + 3) + 1
    term_w  = shutil.get_terminal_size(fallback=(120, 40)).columns
    tasks_per_page = max(1, (term_w - FIXED_W) // (CELL_W + 3))

    def cell(r: dict | None) -> str:
        if r is None:
            return " " * CELL_W
        ok  = "PASS" if r["tests_pass"] else "FAIL"
        tok = f"{r['tok_per_s']:6.1f}t/s" if r.get("tok_per_s", 0) > 0 else "     -   "
        s   = f"{r['wall_s']:6.1f}s"
        return f"{ok}  {tok}  {s}"

    def summary(recs: list[dict | None]) -> str:
        passed  = sum(1 for r in recs if r and r["tests_pass"])
        total_s = sum(r["wall_s"] for r in recs if r)
        toks    = [r["tok_per_s"] for r in recs if r and r.get("tok_per_s", 0) > 0]
        avg_tok = sum(toks) / len(toks) if toks else 0.0
        return f"{passed}/{len(tasks)}  {avg_tok:6.1f}t/s  {total_s:7.1f}s"

    if task_difficulties:
        from collections import Counter
        counts = Counter(task_difficulties.get(t, 1) for t in tasks)
        legend = "  ".join(f"L{lvl}:{n}" for lvl, n in sorted(counts.items()))
    else:
        legend = "L1-L3"

    timeout_note = f"  |  model-timeout: {model_timeout}s" if model_timeout else ""

    # Print one header block (printed once before any pages)
    total_pages = (len(tasks) + tasks_per_page - 1) // tasks_per_page

    def _bar(n_tasks: int) -> str:
        return (
            "+" + "-" * (model_w + 2)
            + "+" + "-" * (SPD_W + 2)
            + "+" + "-" * (SKILL_W + 2)
            + ("+" + "-" * (CELL_W + 2)) * n_tasks
            + "+" + "-" * (SUM_W + 2) + "+"
        )

    # HF repo legend — shown once when any result carries an hf_repo (llama-server runs)
    hf_by_model: dict[str, str] = {}
    for r in results:
        key = dk(r)
        if key not in hf_by_model and r.get("hf_repo"):
            hf_by_model[key] = r["hf_repo"]
    if hf_by_model:
        name_w = max(len(m) for m in models)
        print(f"\nModels ({len(models)}):")
        for i, m in enumerate(models, 1):
            hf = hf_by_model.get(m, "")
            hf_str = f"  hf:{hf}" if hf else ""
            print(f"    {i:2d}. {m:<{name_w}}{hf_str}")

    for page in range(total_pages):
        page_tasks = tasks[page * tasks_per_page : (page + 1) * tasks_per_page]
        bar = _bar(len(page_tasks))

        print()
        print("=" * len(bar))
        page_note = f"  [{page + 1}/{total_pages}]" if total_pages > 1 else ""
        print(f"COMPARISON TABLE{page_note}  (Spd: assumed rank 1=fastest  |  Skill: {legend}{timeout_note})")
        if hardware:
            from lib.hw_snapshot import hw_summary
            print(f"Hardware: {hw_summary(hardware)}")
        print("=" * len(bar))
        print(bar)

        task_hdrs = "".join(f"| {t:<{CELL_W}} " for t in page_tasks)
        print(f"| {'Model':<{model_w}} | {'Spd':^{SPD_W}} | {'Skill':^{SKILL_W}} {task_hdrs}| {'pass  avg tok/s   tot s':<{SUM_W}} |")

        if task_difficulties:
            task_sub = "".join(f"| {'(L'+str(task_difficulties.get(t,1))+') ok  tok/s  wall':<{CELL_W}} " for t in page_tasks)
        else:
            task_sub = "".join(f"| {'ok  tok/s  wall':<{CELL_W}} " for _ in page_tasks)
        print(f"| {'':<{model_w}} | {'est':^{SPD_W}} | {'L1-3':^{SKILL_W}} {task_sub}| {'':<{SUM_W}} |")

        print(bar)

        for model in models:
            page_recs = [idx.get((model, t)) for t in page_tasks]
            all_recs  = [idx.get((model, t)) for t in tasks]
            cells = "".join(f"| {cell(r)} " for r in page_recs)
            rank  = speed_rank[model]
            skill = _skill_level(model, tasks, idx, task_difficulties or {})
            print(f"| {model:<{model_w}} | {rank:^{SPD_W}} | {skill:^{SKILL_W}} {cells}| {summary(all_recs):<{SUM_W}} |")

        print(bar)


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 64)
    print("FAILURE DETAIL")
    print("=" * 64)

    dk = _make_display_key_fn(results)
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_model[dk(r)].append(r)

    any_failures = False
    for model, recs in by_model.items():
        failures = [r for r in recs if not r["tests_pass"]]
        if not failures:
            continue
        any_failures = True
        counts: dict[str, int] = defaultdict(int)
        for r in failures:
            counts[r.get("error_kind") or "unknown"] += 1
        print(f"\nModel : {model}")
        for kind, count in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {count}")
            samples = [r for r in failures if r.get("error_kind") == kind][:1]
            for s in samples:
                detail = (s.get("error_detail") or "")[:120].replace("\n", " ")
                if detail:
                    print(f"    e.g. {detail}")

    if not any_failures:
        print("\nAll tasks passed.")
    print()
