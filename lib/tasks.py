import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from lib.test_results import score_output

TASK_DATA_DIR = Path(__file__).parent.parent / "task_data"


@dataclass
class Task:
    id: str
    description: str
    subdir: str
    editable_files: list[str]
    context_files: list[str]
    test_cmd: list[str]
    test_timeout: int = 60
    setup_cmd: list[str] | None = None
    setup_timeout: int = 120
    difficulty: int = 1  # 1=Easy  2=Medium  3=Hard
    num_ctx: int | None = None          # override global --num-ctx for this task (None = use global)
    min_predict: int | None = None      # floor on --num-predict for this task
    model_timeout: int | None = None    # override global --model-timeout for this task (seconds)
    min_vram_gb: int = 0                # skip task on hardware with less total VRAM (0 = no guard)
    wall_time_budget_s: int | None = None  # PASS_BUT_SLOW threshold; None = no limit
    thinking_budget: int | None = None  # max thinking tokens for thinking models; None = unlimited
    # Partial-credit weights: test-name substring -> weight (first match wins, default 1).
    test_weights: dict[str, float] | None = None


def build_prompt(task: Task, workdir: Path) -> str:
    lines = [
        "You are a coding assistant. Fix the file(s) listed under EDITABLE FILES so all tests pass.",
        "",
        "OUTPUT FORMAT — you must follow this exactly:",
        "",
        "BEGIN_FILE path/to/file.ext",
        "... complete corrected file content ...",
        "END_FILE",
        "",
        "RULES:",
        "- Output ONLY BEGIN_FILE / END_FILE blocks. Nothing else.",
        "- Do NOT use markdown code fences (```), XML, JSON, or any other wrapper.",
        "- Do NOT add preamble, explanation, or commentary before or after the blocks.",
        "- Only edit files listed under EDITABLE FILES.",
        "- Output the complete file content inside each block — not just the changed lines.",
        "",
        f"TASK: {task.description}",
        "",
        "EDITABLE FILES (output corrected versions of ALL of these):",
        "",
    ]
    for rel in task.editable_files:
        content = (workdir / rel).read_text(encoding="utf-8")
        lines += [f"BEGIN_FILE {rel}", content.rstrip("\n"), "END_FILE", ""]

    if task.context_files:
        lines += ["CONTEXT FILES (read-only — do not edit):", ""]
        for rel in task.context_files:
            content = (workdir / rel).read_text(encoding="utf-8")
            lines += [f"--- {rel} ---", content.rstrip("\n"), ""]

    return "\n".join(lines)


def prepare_workdir(task: Task) -> Path:
    src = TASK_DATA_DIR / task.subdir
    tmp = Path(tempfile.mkdtemp(prefix=f"bench_{task.id}_"))
    shutil.copytree(src, tmp, dirs_exist_ok=True)
    return tmp


# Files present in task_data/ that must never reach an export — human-only reference
# solutions or generated cache junk from a prior local test run.
_EXPORT_EXCLUDE_GLOBS = ("*.reference.*", ".pytest_cache", "__pycache__", ".git", "node_modules")


def export_task(task: Task, dest_dir: Path) -> None:
    """Write a self-contained, shareable copy of `task` to `dest_dir`.

    Includes every file needed to run task.setup_cmd / task.test_cmd (matching what
    prepare_workdir gives the harness itself), minus human-only reference solutions.
    Also writes TASK.md (goal + editable/context files + how to check your work) and
    PROMPT.txt (the exact prompt text the harness sends to a model, for chat-only allies).
    """
    if dest_dir.exists() and any(dest_dir.iterdir()):
        raise FileExistsError(f"{dest_dir} already exists and is not empty")

    src = TASK_DATA_DIR / task.subdir
    shutil.copytree(src, dest_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*_EXPORT_EXCLUDE_GLOBS))

    editable_list = "\n".join(f"- `{f}`" for f in task.editable_files)
    context_list = "\n".join(f"- `{f}`" for f in task.context_files) or "(none)"
    setup_line = f"\n**Setup:** `{' '.join(task.setup_cmd)}`\n" if task.setup_cmd else ""
    task_md = f"""# {task.id}

**Difficulty:** L{task.difficulty}

## Goal

{task.description}

## Files you may edit

{editable_list}

## Context files (read-only — do not edit)

{context_list}
{setup_line}
## Check your work

```
{" ".join(task.test_cmd)}
```

All tests must pass. `PROMPT.txt` in this directory is the exact prompt the benchmark harness
sends to a model for this task — useful if your coding assistant works by chat/paste rather
than by reading files directly from this directory.
"""
    (dest_dir / "TASK.md").write_text(task_md, encoding="utf-8")
    (dest_dir / "PROMPT.txt").write_text(build_prompt(task, dest_dir), encoding="utf-8")


def _run_full(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -1, f"Timed out after {timeout}s"


def _truncate(out: str) -> str:
    # Keep the head (primary errors) and tail (summary) — both matter for cascading failures.
    if len(out) > 12000:
        out = out[:6000] + "\n…(truncated)…\n" + out[-4000:]
    return out


def _run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    rc, out = _run_full(cmd, cwd, timeout)
    return rc, _truncate(out)


def run_setup(task: Task, workdir: Path) -> tuple[bool, str]:
    if not task.setup_cmd:
        return True, ""
    rc, out = _run(task.setup_cmd, workdir, task.setup_timeout)
    return rc == 0, out


def run_tests(task: Task, workdir: Path) -> tuple[bool, str]:
    rc, out = _run(task.test_cmd, workdir, task.test_timeout)
    return rc == 0, out


def run_tests_scored(task: Task, workdir: Path) -> tuple[bool, str, dict | None]:
    """run_tests plus partial credit, scored from the full output before truncation drops
    the per-test lines (dotnet test output is often ~100 KB)."""
    rc, out = _run_full(task.test_cmd, workdir, task.test_timeout)
    return rc == 0, _truncate(out), score_output(out, task.test_weights)


# ---------------------------------------------------------------------------
# Built-in tasks
# ---------------------------------------------------------------------------

NODE_SLUGIFY = Task(
    id="node_slugify",
    difficulty=2,
    description=(
        "The slugify function in src/slug.js is broken. Fix it so all tests pass. "
        "The function must: "
        "(1) lowercase the input; "
        "(2) remove apostrophes silently without creating a separator (\"it's\" → \"its\", not \"it-s\"); "
        "(3) replace every remaining run of non-alphanumeric characters "
        "(spaces, hyphens, punctuation, etc.) with a single hyphen; "
        "(4) trim any leading and trailing hyphens from the result."
    ),
    subdir="node_slugify",
    editable_files=["src/slug.js"],
    context_files=["tests/slug.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/slug.test.js"],
    test_timeout=30,
    setup_cmd=["npm", "install", "--prefer-offline"],
    setup_timeout=120,
    min_predict=8000,   # gpt-oss:20b, qwen3.5:35b TRUNCATED at ~4800 default; thinking models need room
)

PYTHON_SAFE_DIV = Task(
    id="python_safe_div",
    difficulty=1,
    description=(
        "calc.safe_div(a, b) must raise ValueError (not ZeroDivisionError) "
        "when b == 0. The current implementation does not do this. "
        "Fix calc.py so all tests pass."
    ),
    subdir="python_safe_div",
    editable_files=["calc.py"],
    context_files=["tests/test_calc.py"],
    test_cmd=["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,   # thinking models (deepseek-r1, qwen3.5) exhaust 400-token default in reasoning
)

DOTNET_SAS = Task(
    id="dotnet_sas",
    difficulty=1,
    description=(
        "SasHelper.GenerateSasUri in src/MicroAzureSas/SasHelper.cs "
        "produces a SAS token with ExpiresOn set in the past. "
        "Fix it so ExpiresOn is approximately 60 minutes in the future. "
        "The ONLY change required is the integer argument to AddMinutes: change -10 to 60. "
        "Do not add, remove, or change any using directives, class structure, "
        "method signatures, or any other line. Output the complete file with only that one value changed."
    ),
    subdir="dotnet_sas",
    editable_files=["src/MicroAzureSas/SasHelper.cs"],
    context_files=["tests/MicroAzureSasTests/SasHelperTests.cs"],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=120,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    min_predict=8000,   # thinking models exhaust 400-token default in reasoning
)

NODE_CSV_PARSER = Task(
    id="node_csv_parser",
    difficulty=3,
    description=(
        "The parseCSV function in src/csv.js is broken. "
        "It uses a naive comma-split that fails on quoted fields. "
        "Fix it so it correctly parses RFC 4180-style CSV: "
        "(1) fields may be wrapped in double-quotes; "
        "(2) a quoted field may contain commas; "
        "(3) a double-quote inside a quoted field is escaped as two consecutive "
        "double-quotes (\"\"\"); "
        "(4) unquoted fields and empty fields must still work as before."
    ),
    subdir="node_csv_parser",
    editable_files=["src/csv.js"],
    context_files=["tests/csv.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/csv.test.js"],
    test_timeout=30,
    min_predict=8000,   # gemma4:26b, qwen3.5:35b TRUNCATED at ~4800 default
)

PYTHON_LRU_CACHE = Task(
    id="python_lru_cache",
    difficulty=2,
    description=(
        "LRUCache.get() in lru_cache.py is broken: it returns the cached value "
        "but does not promote the accessed node to the MRU position. "
        "This means recently-read keys can be incorrectly evicted before "
        "keys that have not been accessed. "
        "Fix get() so that every successful lookup moves the node to the MRU end "
        "of the list, making it the last candidate for eviction."
    ),
    subdir="python_lru_cache",
    editable_files=["lru_cache.py"],
    context_files=["tests/test_lru_cache.py"],
    test_cmd=["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,   # gpt-oss:20b TRUNCATED at ~4800 default
)

PYTHON_MINHEAP = Task(
    id="python_minheap",
    difficulty=3,
    description=(
        "MinHeap._sift_down in minheap.py is missing a check for the right child. "
        "It compares the current node against the left child only — when the right child "
        "is the smallest of the three candidates, it is ignored and the heap property "
        "is violated after pop(). "
        "Add the missing right-child comparison so the smallest of current, left, and right "
        "is always chosen. "
        "Do not change push(), pop(), peek(), __len__(), _sift_up(), or _swap(). "
        "Output the complete file."
    ),
    subdir="python_minheap",
    editable_files=["minheap.py"],
    context_files=["tests/test_minheap.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=12800,  # gpt-oss:20b burns all 2400 default tokens in reasoning — needs extended budget
)

PYTHON_LFU_CACHE = Task(
    id="python_lfu_cache",
    difficulty=3,
    description=(
        "LFUCache in lfu_cache.py has a bug that causes a KeyError during eviction "
        "after certain get/put sequences. "
        "The cache's internal frequency tracking becomes inconsistent under specific access patterns, "
        "causing the next put() that triggers eviction to crash. "
        "Identify the invariant that _promote() fails to maintain and fix it. "
        "Do not change put() or get() directly — the fix belongs in _promote()."
    ),
    subdir="python_lfu_cache",
    editable_files=["lfu_cache.py"],
    context_files=["tests/test_lfu_cache.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=12000,  # gpt-oss:20b TRUNCATED at 6400; raised from 6400
)

PYTHON_LEDGER_BUG = Task(
    id="python_ledger_bug",
    difficulty=4,
    description=(
        "Ledger.transfer() in ledger.py has a bug that corrupts account state when a "
        "transfer fails due to insufficient funds. "
        "Successful transfers work correctly. "
        "When a transfer raises InsufficientFunds, the source account's balance is "
        "correctly left unchanged — but the destination account's balance has already "
        "been modified. "
        "Fix ledger.py so that a failed transfer leaves both accounts in exactly the "
        "state they were in before the call."
    ),
    subdir="python_ledger_bug",
    editable_files=["ledger.py"],
    context_files=["account.py", "tests/test_ledger.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,   # thinking models exhaust 400-token default before emitting BEGIN_FILE
)

NODE_MEMOIZE_BUG = Task(
    id="node_memoize_bug",
    difficulty=3,
    description=(
        "The pricing module's tests are failing with wrong return values. "
        "The pricing logic in src/pricing.js is correct — applyDiscount() and computeTax() "
        "implement their formulas correctly and must not be modified. "
        "The memoize() utility in src/memoize.js is used to cache results for both functions; "
        "it has a bug that causes calls with the same first argument but different subsequent "
        "arguments to return a previously cached result instead of computing a fresh one. "
        "Fix src/memoize.js so all tests pass."
    ),
    subdir="node_memoize_bug",
    editable_files=["src/memoize.js"],
    context_files=["src/pricing.js", "tests/pricing.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/pricing.test.js"],
    test_timeout=30,
    min_predict=8000,   # gpt-oss:20b TRUNCATED at ~4800 default
)

PYTHON_EXPR_EVAL = Task(
    id="python_expr_eval",
    difficulty=4,
    description=(
        "The evaluate() function in expr_eval.py produces incorrect results for "
        "expressions that mix addition/subtraction with multiplication/division. "
        "Standard arithmetic precedence requires multiplication and division to bind "
        "more tightly than addition and subtraction — but the current implementation "
        "inverts this. Parenthesised sub-expressions evaluate correctly. "
        "Fix expr_eval.py so that all tests pass."
    ),
    subdir="python_expr_eval",
    editable_files=["expr_eval.py"],
    context_files=["tests/test_expr_eval.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    num_ctx=32768,       # prompt ~1.1k tokens; thinking models need ~24k generation headroom
    min_predict=24000,  # qwen3.5:35b exhausts 16000 reasoning tokens; raised from 16000
    # NOTE: deepseek-r1:32b loops indefinitely on this task regardless of budget —
    # reasoning spiral ("code is correct. But..."); capability gap, not token budget
)

PYTHON_MULTIFILE_RENAME = Task(
    id="python_multifile_rename",
    difficulty=2,
    description=(
        "The Product dataclass in product.py recently renamed the field price_cents (int, "
        "hundredths of a dollar) to price (float, dollars). "
        "Two dependent modules — inventory.py and reports.py — still use the old "
        "attribute name price_cents and still divide by 100 to convert to dollars. "
        "Fix both files: replace every occurrence of p.price_cents / 100 with p.price "
        "and every occurrence of p.price_cents with p.price. "
        "Output a BEGIN_FILE / END_FILE block for each of the two files."
    ),
    subdir="python_multifile_rename",
    editable_files=["inventory.py", "reports.py"],
    context_files=["product.py", "tests/test_inventory_reports.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    num_ctx=16384,
    min_predict=8000,   # thinking models exhaust 400-token default before emitting BEGIN_FILE
)

PYTHON_DIJKSTRA = Task(
    id="python_dijkstra",
    difficulty=5,
    description=(
        "dijkstra() in dijkstra.py returns incorrect shortest distances and predecessor "
        "maps for certain graph topologies, causing shortest_path() to reconstruct wrong routes. "
        "Fix dijkstra() so all tests pass. Do not modify shortest_path()."
    ),
    subdir="python_dijkstra",
    editable_files=["dijkstra.py"],
    context_files=["tests/test_dijkstra.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=16000,  # gpt-oss:20b TRUNCATED at ~13200 tokens; L5 task needs max budget for thinking models
)

PYTHON_HASHMAP = Task(
    id="python_hashmap",
    difficulty=5,
    description=(
        "HashMap in hashmap.py returns wrong results after certain sequences of "
        "put() and delete() calls. Fix it so all tests pass."
    ),
    subdir="python_hashmap",
    editable_files=["hashmap.py"],
    context_files=["tests/test_hashmap.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=16000,  # gpt-oss:20b TRUNCATED at 8192; raised from 8192
)

NODE_PARATROOPER = Task(
    id="node_paratrooper",
    difficulty=6,
    description=(
        "Implement the Game class in src/game.js — a headless backend for the 1982 arcade game "
        "Paratrooper. The file contains a full specification in comments. "
        "Key rules: a 320×200 coordinate space; turret fixed at (160,185) with angle 0=left/90=up/180=right; "
        "helicopters fly across dropping paratroopers that descend under chutes; shooting a chute "
        "converts the paratrooper to freefall (kills landed troops on impact); shooting the body kills "
        "it outright; jets drop bombs that end the game if they hit the turret; 4 landed troops on "
        "either side ends the game; every shot costs 1 point. "
        "Implement game.input(action), game.tick(), game.getState(), game.isOver(), game.getResult(). "
        "Do not modify tests/game.test.js or package.json."
    ),
    subdir="node_paratrooper",
    editable_files=["src/game.js"],
    context_files=["tests/game.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/game.test.js"],
    test_timeout=60,
    num_ctx=32768,       # measured prompt ≈5.4k tokens; 32k gives ~27k generation budget
    min_predict=24000,   # thinking models need ~15-20k reasoning + ~4k code
    thinking_budget=20000,  # desired cap but NOT honored by current llama-server/GGUF — kept for future builds
    model_timeout=1800,  # complex generation; allow 30 min
)

# ── Paratrooper stepped tasks (L6 split into 4 focused steps) ─────────────────

NODE_PARA_CORE = Task(
    id="node_para_core",
    difficulty=3,
    description=(
        "STEP 1 of 4 — Paratrooper game core structure. "
        "Implement the Game class constructor, input(), tick() (tick counter only), "
        "isOver(), getResult(), and getState() in src/game.js. "
        "DEFAULTS and mulberry32 RNG are already provided. "
        "State fields: tickCount, score, landedLeft, landedRight, over, outcome, turret, "
        "helicopters[], jets[], paratroopers[], bombs[], projectiles[]. "
        "getState() must return shallow copies of arrays. "
        "tick() for this step: guard on over, increment tickCount, reset _pendingInput='none'. "
        "Do not modify tests/game.test.js or package.json."
    ),
    subdir="node_para_core",
    editable_files=["src/game.js"],
    context_files=["tests/game.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/game.test.js"],
    test_timeout=30,
    min_predict=4000,
)

NODE_PARA_TURRET = Task(
    id="node_para_turret",
    difficulty=4,
    description=(
        "STEP 2 of 4 — Paratrooper turret controls and projectile physics. "
        "The constructor, tick(), isOver(), getResult(), and getState() are already implemented. "
        "Implement _processInput() and _updateProjectiles() in src/game.js. "
        "_processInput(): rotate_left decreases angleDeg (clamp 0), rotate_right increases (clamp 180), "
        "fire deducts scoreShotCost and creates a projectile — "
        "rad=(180-angleDeg)*PI/180, dx=cos(rad)*speed, dy=-sin(rad)*speed, projectile starts at turret position. "
        "_updateProjectiles(): move each live projectile by dx/dy; mark alive=false if out of bounds; filter dead. "
        "Do not modify any other method, tests/game.test.js, or package.json."
    ),
    subdir="node_para_turret",
    editable_files=["src/game.js"],
    context_files=["tests/game.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/game.test.js"],
    test_timeout=30,
    min_predict=6000,
)

NODE_PARA_ENTITIES = Task(
    id="node_para_entities",
    difficulty=5,
    description=(
        "STEP 3 of 4 — Paratrooper helicopter and paratrooper entities. "
        "Steps 1-2 are already implemented. Implement four methods in src/game.js: "
        "_spawnHelicopters(): spawn when tickCount>=_nextHelicopterTick; advance interval; "
        "choose side via RNG (<0.5=left); random y in [helicopterMinY,helicopterMaxY]; "
        "push {id,x,y,direction,speed,state:'active',_nextDropTick}. "
        "_updateHelicopters(): move by direction*speed; drop paratrooper at _nextDropTick "
        "(paratrooper: {id,x,y,state:'chute',alive:true}); set state='exiting' when off-screen; filter. "
        "_updateParatroopers(): chute descends at paratrooperDescentRate; freefall at paratrooperFreefallRate; "
        "on landing (y>=groundY): chute→'landed' (record side, increment landedLeft/Right); "
        "freefall→kill overlapping landed paratroopers (|dx|<=paratrooperRadius*2), decrement counter, "
        "then set p.state='dead'. "
        "_checkLoseConditions(): landedLeft>=overrunThreshold→over+outcome='overrun_left'; same for right. "
        "Do not modify any other method, tests/game.test.js, or package.json."
    ),
    subdir="node_para_entities",
    editable_files=["src/game.js"],
    context_files=["tests/game.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/game.test.js"],
    test_timeout=30,
    min_predict=10000,
)

NODE_PARA_COMBAT = Task(
    id="node_para_combat",
    difficulty=6,
    description=(
        "STEP 4 of 4 — Paratrooper jets, bombs, and collision detection. "
        "Steps 1-3 are already implemented. Implement four methods in src/game.js: "
        "_spawnJets(): same pattern as _spawnHelicopters using jetSpawnInterval/_nextJetTick, "
        "jetRadius, jetSpeed; entity has _nextBombTick=tickCount+jetBombInterval. "
        "_updateJets(): same pattern as _updateHelicopters but drops bombs: "
        "{id,x:j.x,y:j.y,state:'falling',alive:true}; uses jetBombInterval and jetRadius for exit. "
        "_updateBombs(): b.y+=bombFallRate per falling bomb; b.state='gone' if y>height; filter gone. "
        "_checkCollisions(): for each live projectile check vs helicopters (state='active'), "
        "jets (state='active'), bombs (state='falling'), and paratroopers (state='chute'/'freefall'). "
        "Chute hit: chuteY=p.y-paratrooperRadius-chuteRadius/2, dist<chuteRadius+projectileRadius → freefall. "
        "Body hit: dist<paratrooperRadius+projectileRadius → dead+scoreParatrooper. "
        "After loop: filter projectiles/helicopters/jets. "
        "Then bombs vs turret: dist<bombRadius+turretRadius → bomb destroyed, turret.alive=false, "
        "over=true, outcome='bomb_hit'. "
        "Do not modify any other method, tests/game.test.js, or package.json."
    ),
    subdir="node_para_combat",
    editable_files=["src/game.js"],
    context_files=["tests/game.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/game.test.js"],
    test_timeout=30,
    num_ctx=16384,   # 400-line stub + 40 tests + description ≈ 9k tokens — exceeds 8192 default
    min_predict=12000,
)

_CONTEXT_PERF_DESC = (
    "An incident archive is provided as context. "
    "Each report has an incident ID, date, severity, engineer, system, resolution code, and notes. "
    "Find the resolution code for incident INCIDENT-5000 and write it — and nothing else — to answer.txt."
)

CONTEXT_8K = Task(
    id="context_8k",
    difficulty=1,
    description=_CONTEXT_PERF_DESC + " Archive: ~100 reports (~5.5k tokens). num_ctx=8192.",
    subdir="context_8k",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=8192,
    min_predict=20,
)

CONTEXT_16K = Task(
    id="context_16k",
    difficulty=1,
    description=_CONTEXT_PERF_DESC + " Archive: ~200 reports (~11k tokens). num_ctx=16384.",
    subdir="context_16k",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=16384,
    min_predict=20,
)

CONTEXT_32K = Task(
    id="context_32k",
    difficulty=1,
    description=_CONTEXT_PERF_DESC + " Archive: ~400 reports (~22k tokens). num_ctx=32768.",
    subdir="context_32k",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=32768,
    min_predict=20,
    wall_time_budget_s=120,  # fast models <30s; >120s indicates KV pressure
)

CONTEXT_64K = Task(
    id="context_64k",
    difficulty=1,
    description=_CONTEXT_PERF_DESC + " Archive: ~800 reports (~44k tokens). num_ctx=65536.",
    subdir="context_64k",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=65536,
    min_predict=20,
    wall_time_budget_s=300,  # fast models <60s; >300s indicates KV pressure (same threshold as 128k)
)

_MULTIHOP_DESC = (
    "An incident archive (~400 reports, ~30k tokens) is provided as context. "
    "Each report has an incident ID, date, severity, engineer, system, resolution code, and notes. "
    "Engineer K. Vasquez appears in exactly two incidents in this archive. "
    "Write the resolution code of the OTHER incident handled by K. Vasquez — and nothing else — to answer.txt."
)

MULTIHOP_FORWARD = Task(
    id="multihop_forward",
    difficulty=3,
    description=(
        _MULTIHOP_DESC +
        " The named anchor incident is INCIDENT-2000 (engineer K. Vasquez, located ~20% into the archive)."
        " The other K. Vasquez incident is located ~75% into the archive."
    ),
    subdir="multihop_forward",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=32768,
    min_predict=8192,  # thinking models burn tokens scanning for the cross-reference
)

MULTIHOP_REVERSE = Task(
    id="multihop_reverse",
    difficulty=3,
    description=(
        _MULTIHOP_DESC +
        " The named anchor incident is INCIDENT-3000 (engineer K. Vasquez, located ~75% into the archive)."
        " The other K. Vasquez incident is located ~20% into the archive — before the anchor."
    ),
    subdir="multihop_reverse",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=32768,
    min_predict=12000,  # gemma4:26b TRUNCATED at 8192; raised from 8192
)

DISTRACTOR_NOTES = Task(
    id="distractor_notes",
    difficulty=2,
    description=(
        "An incident archive (~400 reports, ~30k tokens) is provided as context. "
        "Each report has an incident ID, date, severity, engineer, system, resolution code, and notes. "
        "Find the resolution code for incident INCIDENT-5000 and write it — and nothing else — to answer.txt."
    ),
    subdir="distractor_notes",
    editable_files=["answer.txt"],
    context_files=["documents/incident_archive.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=32768,
    min_predict=20,
)

PYTHON_TOKENIZER = Task(
    id="python_tokenizer",
    difficulty=4,
    description=(
        "The tokenizer has a bug: after processing an escape sequence inside a string, "
        "it transitions back to the wrong state instead of remaining inside the string. "
        "This causes characters following any escape sequence to be tokenized as WORD or UNKNOWN "
        "tokens outside the string rather than being included in the STRING token. "
        "Fix tokenizer.py so all tests pass."
    ),
    subdir="python_tokenizer",
    editable_files=["tokenizer.py"],
    context_files=["tests/test_tokenizer.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=12000,  # gpt-oss:20b TRUNCATED at ~5250; raised from 6400 for thinking models
)

_CODE_ARCHIVE_DESC = (
    "A Python source archive is provided as context. "
    "It contains concatenated Python standard library modules. "
    "One module defines a constant named BENCHMARK_SENTINEL_VALUE. "
    "Find its value and write it — and nothing else — to answer.txt."
)

CONTEXT_128K = Task(
    id="context_128k",
    difficulty=1,
    description=_CODE_ARCHIVE_DESC + " Archive: ~440 KB (~110k tokens). num_ctx=131072.",
    subdir="context_128k",
    editable_files=["answer.txt"],
    context_files=["documents/code_archive.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=131072,
    min_predict=4096,   # thinking models burn tokens before outputting at large context sizes
    model_timeout=3600,  # prompt eval at 128k tokens can take 20-30 min on RAM-bound models
    wall_time_budget_s=300,  # >300s = PASS_BUT_SLOW (qwen3-coder:30b KV spills to RAM at ~3.8 tok/s)
)

CONTEXT_256K = Task(
    id="context_256k",
    difficulty=1,
    description=_CODE_ARCHIVE_DESC + " Archive: ~880 KB (~220k tokens). num_ctx=262144.",
    subdir="context_256k",
    editable_files=["answer.txt"],
    context_files=["documents/code_archive.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=262144,
    min_predict=4096,   # thinking models burn tokens before outputting at large context sizes
    model_timeout=7200,  # prompt eval at 256k tokens can take 60+ min on RAM-bound models
    min_vram_gb=48,     # MoE models with CPU expert offload time out (>2h pp at 220k tokens);
                        # raise to 48 until a fully GPU-resident 256k model is available
)

CSV_NORDIC_PROPERTY = Task(
    id="csv_nordic_property",
    difficulty=3,
    description=(
        "Implement solution.py to process a Norwegian residential property dataset "
        "(data.csv — 5 000 rows × 103 columns, Nordic semicolon-separated CSV, UTF-8). "
        "The script must: "
        "(1) answer 10 data questions and write them to answers.txt, one per line; "
        "(2) select the bottom-25%% and top-25%% of regions by 2023 total purchase sum and "
        "write output.csv (Nordic format) containing only the 1992 and 2022 year-columns "
        "(lowest and highest national totals), sorted ascending by 2023 total. "
        "See the docstrings in solution.py and the tests in test_solution.py for exact "
        "specifications. data.csv is present in the working directory but not shown in full — "
        "use data_sample.csv (title row + header + 5 data rows) to understand the format."
    ),
    subdir="csv_nordic_property",
    editable_files=["solution.py"],
    context_files=["data_sample.csv", "test_solution.py"],
    test_cmd=["python3", "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
    test_timeout=120,
    num_ctx=32768,      # prompt ~6400 tokens; min_predict=20000 needs 26400 total — exceeds old 16384
    min_predict=20000,  # qwen3.5:35b exhausts 12000 reasoning tokens; raised from 12000
    model_timeout=600,  # cold-start + ~12000 token generation exceeds run.sh's 300s default
)

NODE_DEBOUNCE = Task(
    id="node_debounce",
    difficulty=3,
    description=(
        "The debounce() function in src/debounce.js is broken. "
        "It is supposed to delay invoking fn until after delay milliseconds have elapsed "
        "since the last call — rapid successive calls should coalesce into one. "
        "The current implementation does not do this. "
        "Fix src/debounce.js so all tests pass."
    ),
    subdir="node_debounce",
    editable_files=["src/debounce.js"],
    context_files=["tests/debounce.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/debounce.test.js"],
    test_timeout=30,
    min_predict=8000,   # thinking models exhaust 400-token default in reasoning
)

PYTHON_MERGE_INTERVALS = Task(
    id="python_merge_intervals",
    difficulty=4,
    description=(
        "merge_intervals() in merge_intervals.py takes a list of [start, end] integer "
        "intervals and should return a minimal sorted list of non-overlapping merged intervals. "
        "It returns wrong results for certain inputs. "
        "Fix merge_intervals.py so all tests pass."
    ),
    subdir="python_merge_intervals",
    editable_files=["merge_intervals.py"],
    context_files=["tests/test_merge_intervals.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,   # thinking models exhaust 400-token default in reasoning
)

AWK_CSV_STATS = Task(
    id="awk_csv_stats",
    difficulty=3,
    description=(
        "stats.awk reads sales.csv and should print per-region total sales to stdout, "
        "one line per region in the format 'region: total' (two decimal places, "
        "e.g. 'east: 330.25'). "
        "The output is incorrect. Fix stats.awk so all tests pass."
    ),
    subdir="awk_csv_stats",
    editable_files=["stats.awk"],
    context_files=["sales.csv", "tests/test_stats.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,   # thinking models exhaust 400-token default in reasoning
)

JAVA_WORD_FREQ = Task(
    id="java_word_freq",
    difficulty=3,
    description=(
        "WordFreq.topK(int k) in WordFreq.java should return the k most frequent words "
        "in descending order of frequency. "
        "It returns the wrong words. Fix WordFreq.java so all tests pass."
    ),
    subdir="java_word_freq",
    editable_files=["WordFreq.java"],
    context_files=["WordFreqTest.java"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,   # thinking models exhaust 400-token default in reasoning
)

PYTHON_CONFIG_LOADER = Task(
    id="python_config_loader",
    difficulty=2,
    description=(
        "load_config() in config.py reads APP_HOST, APP_PORT, APP_DEBUG, APP_MAX_CONN, and APP_NAME "
        "from environment variables with typed defaults. It has two bugs: "
        "(1) string values are not stripped of leading/trailing whitespace before use or conversion, "
        "so APP_PORT='  9000  ' causes a ValueError in int(); "
        "(2) an environment variable explicitly set to an empty string is not treated as absent — "
        "the caller's default is ignored and the empty string is used instead. "
        "Fix config.py so all tests pass."
    ),
    subdir="python_config_loader",
    editable_files=["config.py"],
    context_files=["tests/test_config_loader.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,
)

BASH_PREFLIGHT = Task(
    id="bash_preflight",
    difficulty=2,
    description=(
        "preflight.sh checks that required commands (git, python3, curl) are on PATH "
        "and that required environment variables (DATABASE_URL, APP_SECRET) are set and non-empty. "
        "It has two bugs: "
        "(1) it always prints 'OK' even when checks fail; "
        "(2) it always exits 0 regardless of whether any checks failed. "
        "Fix preflight.sh so it prints 'OK' and exits 0 only when all checks pass, "
        "and exits 1 with MISSING_VAR / MISSING_CMD messages to stderr when any check fails."
    ),
    subdir="bash_preflight",
    editable_files=["preflight.sh"],
    context_files=["tests/test_preflight.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=30,
    min_predict=8000,
)

NODE_EXPRESS_VALIDATION = Task(
    id="node_express_validation",
    difficulty=3,
    description=(
        "The POST /items route in src/router.js has four bugs: "
        "(1) returns HTTP 200 instead of 201 on success; "
        "(2) does not validate that price is a number (accepts strings like 'free'); "
        "(3) does not validate that price is positive (accepts zero and negative values); "
        "(4) does not reject whitespace-only names (accepts '   ' as a valid name). "
        "The stored item's name should be the trimmed value. "
        "Fix src/router.js so all tests pass. Do not modify src/app.js, tests/router.test.js, or package.json."
    ),
    subdir="node_express_validation",
    editable_files=["src/router.js"],
    context_files=["src/app.js", "tests/router.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/router.test.js"],
    test_timeout=30,
    setup_cmd=["npm", "install", "--prefer-offline"],
    setup_timeout=120,
    min_predict=8000,
)

PYTHON_FASTAPI_ENDPOINT = Task(
    id="python_fastapi_endpoint",
    difficulty=3,
    description=(
        "The products API in products.py has three bugs: "
        "(1) POST /products returns HTTP 200 instead of 201 (missing status_code=201 on the decorator); "
        "(2) GET /products/{product_id} returns None for missing IDs causing a 500 — it should raise HTTPException(404); "
        "(3) POST /products accepts zero, negative, and whitespace-only names — "
        "price must be > 0 and name must be non-blank after stripping whitespace. "
        "Use Pydantic field constraints / validators for price and name. "
        "Fix products.py so all tests pass."
    ),
    subdir="python_fastapi_endpoint",
    editable_files=["products.py"],
    context_files=["tests/test_products.py"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short", "-W", "ignore::DeprecationWarning"],
    test_timeout=30,
    setup_cmd=["python3", "-m", "pip", "install", "-q", "fastapi", "httpx"],
    setup_timeout=120,
    min_predict=8000,
)

# Game-dev tasks: Unity-client C# (compiled against a minimal UnityEngine shim, with
# Unity's netstandard2.1 + C# 9 constraints) and Node.js authoritative-server logic.
UNITY_CONSTRAINTS = (
    " The project follows Unity's scripting constraints: it targets netstandard2.1 with "
    "LangVersion 9.0, so C# 10+ features (file-scoped namespaces, global usings, record structs, "
    "'required' members, collection expressions) do not compile. The only UnityEngine API that "
    "exists is what shim/UnityShim/UnityEngine.cs defines."
)
UNITY_CONTEXT = ["shim/UnityShim/UnityEngine.cs", "src/GameClient/GameClient.csproj"]

CS_COORD_CONVERT = Task(
    id="cs_coord_convert",
    difficulty=2,
    description=(
        "ThreeToUnity in src/GameClient/CoordConvert.cs converts state from a Node.js game server "
        "that uses Three.js conventions (right-handed, Y-up, centimeters, radians, quaternions as "
        "[x, y, z, w]) into Unity conventions (left-handed, Y-up, meters, degrees). The conversion "
        "mirrors the Z axis. It has several bugs. Required behavior: "
        "(1) Position and Velocity negate Z and convert centimeters to meters; "
        "(2) Rotation returns the mirrored quaternion for the same physical rotation, normalized "
        "(server quaternions may not be unit length); "
        "(3) YawDegrees converts a Three.js rotation.y angle to the equivalent Unity Y rotation in "
        "degrees, always in the range [0, 360); "
        "(4) PositionToServer is the exact inverse of Position; "
        "(5) null arrays, arrays of the wrong length, and NaN or infinite values throw an "
        "ArgumentException (or subclass)." + UNITY_CONSTRAINTS
    ),
    subdir="cs_coord_convert",
    editable_files=["src/GameClient/CoordConvert.cs"],
    context_files=["tests/GameClientTests/CoordConvertTests.cs"] + UNITY_CONTEXT,
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,      # ~6k-token prompt (shim included) + 12k thinking budget
    min_predict=12000,  # 8000 truncated thinking models mid-reasoning (quest:35b, 2026-10-08)
    test_weights={"Rotation_": 2.0, "RejectsMalformedInput": 0.5},
)

CS_COORD_BAM = Task(
    id="cs_coord_bam",
    difficulty=3,
    description=(
        "EngineCoords in src/GameClient/EngineCoords.cs was ported from a Three.js client and still uses "
        "Three.js conventions; make it correct for Unity. Engine: x east, y north, z up (altitude), 256 "
        "units per meter, integers; headings are BAM, 0..65535 per full turn, 0 = east, counter-clockwise "
        "toward north. Unity: x east, y up, z north, left-handed, and Quaternion.Euler(0, yaw, 0) turns "
        "Vector3.forward clockwise (seen from above) by yaw degrees. Required behavior: "
        "(1) Position(x, y, altitude) returns meters as (x, altitude, y) / 256, keeping fractions; "
        "(2) ToUnits(meters) converts back exactly like the server's JavaScript Math.round(meters * 256) "
        "(halves round toward positive infinity, so 2.5 -> 3 and -2.5 -> -2), and throws an "
        "ArgumentException (or subclass) for NaN or infinity; "
        "(3) YawDegrees(bam) is the Unity yaw that faces the heading, in [0, 360); Rotation(bam) = "
        "Quaternion.Euler(0, YawDegrees(bam), 0), so Rotation(bam) * Vector3.forward equals Forward(bam); "
        "(4) Forward(bam) is the unit vector of the heading in Unity space; "
        "(5) YawDegrees and Forward throw ArgumentOutOfRangeException for bam outside 0..65535; "
        "(6) HeadingFromYaw(yaw) is the inverse of YawDegrees for any finite yaw (including negative or "
        "above 360), rounding half a BAM up like Math.round, wrapped into 0..65535." + UNITY_CONSTRAINTS
    ),
    subdir="cs_coord_bam",
    editable_files=["src/GameClient/EngineCoords.cs"],
    context_files=["tests/GameClientTests/EngineCoordsTests.cs"] + UNITY_CONTEXT,
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,      # ~6k-token prompt (shim included) + 12k thinking budget
    min_predict=12000,  # 8000 truncated thinking models mid-reasoning (quest:35b, 2026-10-08)
    test_weights={"RotationTurnsUnityForward": 2.0, "MovingAlongForward": 2.0, "_Rejects": 0.5},
)

CS_PORT_MOVEMENT = Task(
    id="cs_port_movement",
    difficulty=3,
    description=(
        "Port boombrawl's movement integrator to C#: implement WorldToCell and StepEntity in "
        "src/GameClient/Movement.cs as an exact port of the read-only js/movement.mjs, including the "
        "constants and helpers it imports from js/const.mjs and js/fixedmath.mjs. The game server runs the "
        "JavaScript every tick and the Unity client's prediction runs this port, so every result must be "
        "identical to the JavaScript for every input: integer math only, the same clamps, and the same "
        "floor division (JavaScript Math.floor, also for negative values). The tests replay thousands of "
        "steps recorded from the JavaScript on a real captured arena." + UNITY_CONSTRAINTS
    ),
    subdir="cs_port_movement",
    editable_files=["src/GameClient/Movement.cs"],
    context_files=[
        "js/movement.mjs",
        "js/const.mjs",
        "js/fixedmath.mjs",
        "tests/GameClientTests/MovementPortTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,
    min_predict=12000,
    test_weights={"CornerAssistThreshold": 3.0, "RandomWalks": 2.0},
)

CS_PORT_HEIGHTMAP = Task(
    id="cs_port_heightmap",
    difficulty=4,
    description=(
        "Port CarrierDominion's island terrain to C#: implement SkirtRadius and IslandHeightAt in "
        "src/GameClient/Heightmap.cs as an exact port of skirtRadius / islandHeightAt in the read-only "
        "js/engine/heightmap.js, including everything they use from js/shared/noise.js (value noise, "
        "fBm, the lattice hash), js/shared/fixed.js (floorDiv, mulDiv, isqrt) and js/shared/prng.js "
        "(mul32). The server collides with this terrain and the Unity client builds meshes from it, so "
        "every height must equal the JavaScript's exactly: integer math only (JavaScript numbers are exact "
        "below 2^53 here, so C# long covers them), the same floor divisions, and the same 32-bit "
        "behaviour of ^ and >>>. Island (read-only src/GameClient/Island.cs) has int fields, as on the "
        "wire. The tests compare against ~14,000 heights sampled from the JavaScript on real captured "
        "islands." + UNITY_CONSTRAINTS
    ),
    subdir="cs_port_heightmap",
    editable_files=["src/GameClient/Heightmap.cs"],
    context_files=[
        "js/engine/heightmap.js",
        "js/shared/noise.js",
        "js/shared/fixed.js",
        "js/shared/prng.js",
        "src/GameClient/Island.cs",
        "tests/GameClientTests/HeightmapPortTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=32768,      # ~9k-token prompt (four real JS files) + 12k thinking budget
    min_predict=12000,
    test_weights={"CapturedIslands": 3.0, "SeedNearIntMax": 1.0},
)

CS_PORT_WEBAUDIO = Task(
    id="cs_port_webaudio",
    difficulty=4,
    description=(
        "Port boombrawl's browser sound effects (read-only js/sound.js, Web Audio) to an offline C# "
        "renderer: implement src/GameClient/Synth.cs (types in the read-only src/GameClient/SynthTypes.cs). "
        "(1) Effects: every effect in sound.js (tick, go, boom, death, shrink, win) as Layer arrays with the "
        "same frequencies, durations, volumes, waveforms, slides and start offsets, using sound.js's defaults; "
        "(2) ExponentialRamp(from, to, t, dur) must follow Web Audio's exponentialRampToValueAtTime exactly and "
        "hold the end value after dur; "
        "(3) Lowpass(cutoffHz, q, sampleRate) returns the a0-normalised biquad coefficients of Web Audio's "
        "BiquadFilterNode type 'lowpass' exactly as the Web Audio specification defines them (note how that "
        "node interprets Q); "
        "(4) Render(layers, seed) mixes the layers into a 48 kHz buffer as the browser plays them: tones decay "
        "from their volume to 0.001 over dur and stop 0.02 s later, pitch slides ramp exponentially to "
        "max(20, slideTo); noise bursts last dur and pass through the lowpass (default Q) whose cutoff ramps "
        "from 2*freq to max(40, freq/4); the buffer is as long as the latest layer; same seed, same output." + UNITY_CONSTRAINTS
    ),
    subdir="cs_port_webaudio",
    editable_files=["src/GameClient/Synth.cs"],
    context_files=[
        "js/sound.js",
        "src/GameClient/SynthTypes.cs",
        "tests/GameClientTests/SynthPortTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,
    min_predict=12000,
    test_weights={"Lowpass_Coefficients": 2.0, "BoostsTheCutoff": 3.0, "Effects_MatchSoundJs": 2.0},
)

CS_TICK_INTERP = Task(
    id="cs_tick_interp",
    difficulty=4,
    description=(
        "Implement TickInterpolator in src/GameClient/TickInterpolator.cs (types in the read-only "
        "src/GameClient/TickTypes.cs): Unity-side smoothing between CarrierDominion server views that "
        "interpolates on the server's tick, not on arrival time, because at time compression the server sends "
        "its ticks in bursts (x16: sixteen views every 50 ms). Required behavior: "
        "(1) Push(view, arrivalSeconds) ignores a view whose tick is not greater than Latest's; keeps at most "
        "Capacity views (dropping the oldest); then measures Rate: take the oldest buffered view that arrived "
        "within 1 s of the newest arrival, and if that span is at least 0.2 s, Rate = tick difference / span; "
        "(2) SetNominalRate sets Rate only while no rate has been set or measured yet; "
        "(3) Advance(dt), once per frame, does nothing when empty; otherwise target = Latest.tick - Rate * "
        "DelaySeconds, render = (previous RenderTick, or target on the first call) + Rate * dt, then render += "
        "(target - render) * (1 - e^(-5 dt)), clamped to [oldest buffered tick, Latest.tick]; RenderTick is 0 "
        "before the first Advance; "
        "(4) Sample(tick) returns null when empty, the oldest view if tick is before it, Latest if tick is at or "
        "after it, else the bracketing pair (older.tick <= tick < newer.tick) interpolated with t = (tick - "
        "older.tick) / (newer.tick - older.tick): the result's View is the newer view and contains exactly its "
        "carriers and units; positions lerp from the older view's pose, headings turn via ShortTurn; a mover "
        "absent from the older view keeps its newer pose; "
        "(5) ShortTurn(from, to) is the BAM difference (65536 per turn) the short way round, in -32768..32767." + UNITY_CONSTRAINTS
    ),
    subdir="cs_tick_interp",
    editable_files=["src/GameClient/TickInterpolator.cs"],
    context_files=[
        "src/GameClient/TickTypes.cs",
        "tests/GameClientTests/TickInterpolatorTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,
    min_predict=12000,
    test_weights={"CapturedRun": 3.0, "BurstyServer": 2.0, "Rate_IsMeasured": 2.0},
)

CS_WS_ABORT_RECONNECT = Task(
    id="cs_ws_abort_reconnect",
    difficulty=4,
    description=(
        "Bug report from a Unity client's network layer: simulating a network drop by calling Abort() on the "
        "socket (as a phone suspend or Wi-Fi loss does) never produces a reconnect - the connection just goes "
        "silent. Fix ConnectionLoop in src/GameClient/ConnectionLoop.cs (the socket abstraction is the "
        "read-only src/GameClient/IMessageSocket.cs; read its documentation). Required behavior of RunAsync: "
        "(1) connect, then deliver every received message to onMessage in order; "
        "(2) ANY loss of the connection - the server closing cleanly (ReceiveAsync returns null, reason "
        "\"closed by server\"), a socket error (reason = the exception's Message), a failed connect, or the "
        "socket being aborted - calls onClosed exactly once with the reason and then requestReconnect "
        "exactly once; "
        "(3) a client shutdown - the CancellationToken passed to RunAsync is cancelled - ends RunAsync quietly "
        "without calling onClosed or requestReconnect, whatever exception the socket throws while shutting "
        "down." + UNITY_CONSTRAINTS
    ),
    subdir="cs_ws_abort_reconnect",
    editable_files=["src/GameClient/ConnectionLoop.cs"],
    context_files=[
        "src/GameClient/IMessageSocket.cs",
        "tests/GameClientTests/ConnectionLoopTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,
    min_predict=12000,
    test_weights={"AbortedSocket": 3.0, "ShutdownWhileTheSocketFails": 2.0},
)

CS_RECONNECT_POLICY = Task(
    id="cs_reconnect_policy",
    difficulty=3,
    description=(
        "Implement the reconnect policy and seat URL handling of a Unity game client in "
        "src/GameClient/Reconnect.cs, matching the browser clients. ReconnectPolicy: NextDelay() returns "
        "the seconds to wait before the next attempt - 1 the first time, then each delay is the previous "
        "one times 1.7 rounded to 3 decimals, capped at 5 (1, 1.7, 2.89, 4.913, 5, 5, ...); OnConnected() "
        "resets it so the next delay is 1 again; TryBeginConnect() returns false while a connect is already "
        "in progress (until EndConnect()), so attempts never overlap. SeatUrl.WithToken(url, token): the seat "
        "token rides the socket URL as the query parameter token, escaped so any token text round-trips "
        "exactly; keep scheme, host, port, path and every other query parameter, replace an existing token "
        "parameter, and return url unchanged when token is null or empty. SeatUrl.ForLog(url): the URL with "
        "its query and fragment removed - the token must never reach a log." + UNITY_CONSTRAINTS
    ),
    subdir="cs_reconnect_policy",
    editable_files=["src/GameClient/Reconnect.cs"],
    context_files=[
        "tests/GameClientTests/ReconnectTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,
    min_predict=12000,
    test_weights={"EscapesTheToken": 2.0, "ForLog": 2.0},
)

CS_WS_CLIENT = Task(
    id="cs_ws_client",
    difficulty=4,
    description=(
        "Implement WebSocketConnection in src/GameClient/WebSocketConnection.cs: a minimal RFC 6455 "
        "WebSocket client for a Unity game, on a TcpClient with blocking reads (SslStream for wss://), "
        "because the Unity Linux player's ClientWebSocket stalls reads while a write is in flight. One "
        "thread calls ReadMessage while others call SendText. Required: the opening handshake (GET with "
        "path and query, Host with the port when it is not the default, a fresh random 16-byte "
        "Sec-WebSocket-Key per connection, version 13), checking the status is 101 and that "
        "Sec-WebSocket-Accept is base64(SHA1(key + \"258EAFA5-E914-47DA-95CA-C5AB0DC85B11\")), else "
        "IOException; client frames final, masked with a fresh random 4-byte key, using the 7-bit, 16-bit "
        "and 64-bit length forms; frames from different threads must never interleave; ReadMessage "
        "joins fragmented messages, answers a ping with a pong carrying the same payload (also between "
        "fragments), ignores pongs, throws IOException when a message exceeds maxMessageBytes or the "
        "connection drops, and on a close frame echoes the close and returns null with closeReason "
        "\"<code> <reason>\" trimmed (\"1005\" without a code); Abort() drops the socket so a blocked "
        "reader returns." + UNITY_CONSTRAINTS
    ),
    subdir="cs_ws_client",
    editable_files=["src/GameClient/WebSocketConnection.cs"],
    context_files=[
        "tests/GameClientTests/WebSocketConnectionTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=240,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=32768,
    min_predict=12000,
    test_weights={"Handshake_": 2.0, "FirstFrame": 2.0, "JoinsFragments": 2.0, "ConcurrentSends": 2.0},
)

CS_PRIMITIVE_COMPOSE = Task(
    id="cs_primitive_compose",
    difficulty=4,
    description=(
        "Port ship parts built from three.js primitives (js/parts.js, real code from the browser client) "
        "to Unity transforms in src/GameClient/PartPort.cs. Each method builds its part under the model's "
        "root transform and returns the transform that carries the part's mesh: the Primitives mesh named "
        "in the comment (src/GameClient/Primitives.cs, read-only), used unchanged. Add holder GameObjects "
        "in between where one transform is not enough. Every vertex of the primitive must land exactly "
        "where the browser draws it, mirrored into Unity's axes: a three.js model-space point (x, y, z) "
        "is (x, y, -z) in Unity model space. Unity's Transform applies scale, then rotation, then "
        "position; three.js geometry.rotateX/Y/Z and geometry.scale transform the vertices themselves, "
        "in call order, before the mesh's own scale, rotation and position." + UNITY_CONSTRAINTS
    ),
    subdir="cs_primitive_compose",
    editable_files=["src/GameClient/PartPort.cs"],
    context_files=[
        "js/parts.js",
        "src/GameClient/Primitives.cs",
        "tests/GameClientTests/PartPortTests.cs",
    ] + UNITY_CONTEXT,
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=32768,
    min_predict=12000,
    test_weights={"mantaDelta": 2.0, "turretRail": 2.0, "carrierBow": 2.0},
)

CS_MAIN_THREAD_DISPATCH = Task(
    id="cs_main_thread_dispatch",
    difficulty=3,
    description=(
        "MainThreadDispatcher in src/GameClient/MainThreadDispatcher.cs lets network worker "
        "threads hand work to Unity's main thread, which calls Drain() once per frame. The current "
        "implementation is broken. Required behavior: "
        "(1) the constructor throws ArgumentOutOfRangeException if capacity or maxPerFrame is < 1; "
        "(2) Enqueue is safe to call from any number of threads concurrently, never blocks while an "
        "action is running, and throws ArgumentNullException for null; "
        "(3) the queue is bounded: when Pending equals Capacity, Enqueue rejects the new action, "
        "returns false and increments DroppedCount; "
        "(4) Drain runs at most MaxPerFrame actions in FIFO order and returns how many it ran; "
        "(5) actions enqueued while Drain is running (including by a drained action) wait for the "
        "next Drain call; "
        "(6) an action that throws is logged with Debug.LogException, increments ExceptionCount, "
        "still counts toward the budget and the return value, and does not stop the drain; "
        "(7) actions run without holding any lock, so other threads can Enqueue meanwhile; "
        "(8) the first thread that calls Drain becomes the main thread; Drain from any other thread "
        "afterwards throws InvalidOperationException." + UNITY_CONSTRAINTS
    ),
    subdir="cs_main_thread_dispatch",
    editable_files=["src/GameClient/MainThreadDispatcher.cs"],
    context_files=["tests/GameClientTests/MainThreadDispatcherTests.cs"] + UNITY_CONTEXT,
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,      # ~6k-token prompt (shim included) + 12k thinking budget
    min_predict=12000,  # 8000 truncated thinking models mid-reasoning (quest:35b, 2026-10-08)
    test_weights={"ConcurrentEnqueue": 2.0, "WorkEnqueuedDuringDrain": 2.0, "Constructor_Rejects": 0.5, "Enqueue_Null": 0.5},
)

CS_PROTOCOL_CODEC = Task(
    id="cs_protocol_codec",
    difficulty=4,
    description=(
        "Implement Decode and EncodeInput in src/GameClient/SnapCodec.cs: the Unity client's side of "
        "a Node.js game server's JSON WebSocket protocol, using Newtonsoft.Json (JToken.Parse). Types are "
        "in the read-only src/GameClient/Messages.cs. Every message is a JSON object whose string field "
        "\"t\" names its type. Decode rules: "
        "(1) unparseable JSON throws ProtocolException(BadJson); a non-object or a missing/non-string "
        "\"t\" throws BadShape; an unknown \"t\" throws UnknownType; "
        "(2) \"hello\" carries v (protocol version), id (this client's player id) and roster "
        "(objects with id, name, color, bot as 0/1). v must be checked first: missing or non-integer is "
        "BadField, outside [MinSupportedVersion, ProtocolVersion] is VersionMismatch. Version 2 roster "
        "entries have no color (use 0); version 3 requires it. A hello replaces the codec's Roster "
        "entirely and returns a HelloMessage; "
        "(3) \"snap\" carries tick, phase, and p / b: arrays of positional rows whose value order is "
        "PlayerFields / BombFields. \"st\" codes are a=Alive, d=Dead, anything else Waiting. Name, "
        "color and bot come from the Roster; ids not in the Roster get name \"?\", color 0, bot false; "
        "(4) \"reject\" carries a string reason; "
        "(5) unknown extra fields and extra trailing row values are ignored (newer servers add them), "
        "but a missing required field, a row shorter than its field list, a wrong JSON type, or an "
        "integer field that is not a whole number fitting in a 32-bit int throws BadField. "
        "EncodeInput produces exactly {\"t\":\"in\",\"seq\":N,\"dx\":N,\"dy\":N} with no "
        "whitespace and that key order, appending ,\"b\":1 only when bomb is true; it throws an "
        "ArgumentException (or subclass) for negative seq, dx or dy outside -1..1, or diagonal "
        "movement (both non-zero)." + UNITY_CONSTRAINTS
    ),
    subdir="cs_protocol_codec",
    editable_files=["src/GameClient/SnapCodec.cs"],
    context_files=[
        "src/GameClient/Messages.cs",
        "tests/GameClientTests/SnapCodecTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,      # prompt + 12k thinking budget
    min_predict=12000,
    test_weights={"Snap_DecodesPositionalRows": 2.0, "Hello_V3_PopulatesRoster": 2.0, "EncodeInput_MatchesServerFormatExactly": 2.0, "EncodeInput_RejectsInvalidInput": 0.5},
)

CS_SNAPSHOT_INTERP = Task(
    id="cs_snapshot_interp",
    difficulty=4,
    description=(
        "Implement SnapshotInterpolator in src/GameClient/SnapshotInterpolator.cs (types in the read-only "
        "src/GameClient/Snapshots.cs). A Unity client renders remote entities DelayMs behind real time, "
        "interpolating between buffered authoritative snapshots. Required behavior: "
        "(1) the constructor throws ArgumentOutOfRangeException for delayMs < 0, capacity < 2 or "
        "maxExtrapolationMs < 0; Push(null) throws ArgumentNullException; "
        "(2) Push ignores a snapshot whose atMs is earlier than the newest buffered one or whose Tick is not "
        "greater than the newest buffered Tick; beyond Capacity the oldest snapshot is evicted; Count is the "
        "number buffered; "
        "(3) Sample(nowMs) returns null when empty. Render time is nowMs - DelayMs. The bracketing pair is "
        "the latest snapshot with atMs <= render time (older) and the first with atMs > render time (newer); "
        "interpolate with t = (render - older.atMs) / (newer.atMs - older.atMs), clamped to [0, 1]. The "
        "entity list comes from the newer snapshot of the pair, but an entity absent from the newest "
        "buffered snapshot is never returned. "
        "(4) an entity with no previous state in the older snapshot, with Teleported set in the newer one, "
        "or that moved more than TeleportDistanceUnits (Euclidean, in fixed-point units) is placed at its "
        "newer position without interpolation; "
        "(5) Heading (brads, 0..255 per full turn) interpolates along the shortest arc, wrapping through 0; "
        "Rotation = Quaternion.Euler(0, brads * 360 / 256, 0) and follows Heading only, never the direction "
        "of travel; MotionHeading is Mathf.Atan2(dY, dX) of the displacement between the two snapshots "
        "used, or null when that displacement is zero or the entity was not interpolated/extrapolated "
        "from a previous state; Position = (X / 256, 0, Y / 256); "
        "(6) if render time is before every buffered snapshot, return the oldest snapshot's entities as-is "
        "with MotionHeading null; "
        "(7) if no snapshot is newer than render time, extrapolate each newest entity linearly from its "
        "state in the previous buffered snapshot, by min(render - newest.atMs, MaxExtrapolationMs); "
        "entities without a previous state, teleported or jumping too far are held at their newest "
        "position; with only one snapshot everything holds; Heading is not extrapolated." + UNITY_CONSTRAINTS
    ),
    subdir="cs_snapshot_interp",
    editable_files=["src/GameClient/SnapshotInterpolator.cs"],
    context_files=["src/GameClient/Snapshots.cs", "tests/GameClientTests/SnapshotInterpolatorTests.cs"] + UNITY_CONTEXT,
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,      # ~10k-token prompt (shim included) + 12k thinking budget
    min_predict=12000,
    test_weights={"Sample_InterpolatesDelayBehind": 2.0, "EntityMissingFromNewestSnapshot": 2.0, "Constructor_Rejects": 0.5},
)

CS_PREDICT_RECONCILE = Task(
    id="cs_predict_reconcile",
    difficulty=5,
    description=(
        "Predictor in src/GameClient/Predictor.cs does client-side prediction and server reconciliation "
        "for the local player of a real-time game whose Node.js server is authoritative. It must run the "
        "exact integer math of the read-only src/GameClient/Movement.cs so the prediction matches the "
        "server tick for tick, but it has several bugs. Required behavior: "
        "(1) the constructor and OnSnapshot throw ArgumentNullException for null arguments; "
        "(2) SetDirection throws ArgumentOutOfRangeException for values outside -1..1 and keeps movement "
        "single-axis (if dx != 0, dy becomes 0); "
        "(3) Tick increments the sequence number and always sends an InputCommand, but only while Active "
        "does it also simulate the input locally (Movement.Step with the current speed) and remember it as "
        "pending; "
        "(4) OnSnapshot ignores a snapshot whose Tick is not greater than the last one applied; if the local "
        "player is missing it deactivates and clears pending inputs; otherwise it takes the speed from "
        "SpeedLevel (Movement.SpeedForLevel) and resets X/Y to the server position, then: in phase \"play\" "
        "with status \"alive\" it becomes Active, discards every pending input the server has applied "
        "(Seq <= the snapshot's Seq) and replays the remaining ones in order with that speed; in any other "
        "phase or status it deactivates and clears pending inputs; "
        "(5) RenderPosition is (X / 256, 0, Y / 256) in meters, keeping fractions." + UNITY_CONSTRAINTS
    ),
    subdir="cs_predict_reconcile",
    editable_files=["src/GameClient/Predictor.cs"],
    context_files=[
        "src/GameClient/Movement.cs",
        "src/GameClient/PredictionTypes.cs",
        "tests/GameClientTests/PredictorTests.cs",
    ] + UNITY_CONTEXT,
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,      # ~11k-token prompt (shim included) + 12k thinking budget
    min_predict=12000,
    test_weights={"ConvergesExactly": 3.0, "PredictionMatchesServerEveryTick": 3.0, "Reconcile_": 2.0, "Constructor_Rejects": 0.5},
)

NODE_ROOM_AUTHORITY = Task(
    id="node_room_authority",
    difficulty=4,
    description=(
        "Implement createRoom in src/room.js: the authoritative match room of a Node.js game server that "
        "receives raw WebSocket text frames (string or Buffer) from untrusted clients. The returned object "
        "has connect(connId, team) (team -1 = spectator; connecting again replaces the connection), "
        "disconnect(connId), receive(connId, raw) returning {ok: true} or {ok: false, reason} with a "
        "REJECT value, tick() returning {tick, applied}, and units() returning copies "
        "[{id, team, x, y}] sorted by id. Commands are {type: 'move', seq, unitId, x, y} and "
        "{type: 'stop', seq, unitId}. receive checks, in exactly this order: unknown connection -> "
        "notConnected; frame over MAX_FRAME_BYTES UTF-8 bytes -> badFrame; invalid JSON -> badJson; not a "
        "plain object or no string type -> badShape; type 'tick' -> serverOwned; any other type that is not "
        "move/stop -> unknownType (beware names like 'constructor' or 'toString'); spectator -> spectator; "
        "then one token is taken from the seat's token bucket, or rateLimited if none is left; then fields: "
        "seq a non-negative integer, unitId an integer, and for move x/y integers inside 0..width-1 / "
        "0..height-1, else badField; seq not greater than the last ACCEPTED seq of this connection -> "
        "staleSeq; unknown unit -> noSuchUnit; unit of another team -> notYourUnit. The team always comes "
        "from the connection; team or player fields inside the message are ignored. Token buckets are per "
        "team (shared by every connection of that team and kept across reconnects): they start full at "
        "cmdBurst and refill continuously at cmdRefillPerSec using the injected now() in milliseconds, "
        "capped at cmdBurst. Accepted commands queue until tick(), which increments the tick number, applies "
        "queued commands in arrival order (move sets the unit's target, stop clears it), skips commands "
        "from connections that disconnected since (a reconnect gets a fresh seq history and does not revive "
        "them), lists each applied one as {team, type, unitId}, then moves every unit with a target one cell "
        "toward it on each axis (in id order), clearing the target on arrival."
    ),
    subdir="node_room_authority",
    editable_files=["src/room.js"],
    context_files=["tests/room.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/room.test.js"],
    test_timeout=60,
    num_ctx=24576,      # the 8192 default cut thinking models off mid-file (2026-10-08)
    min_predict=12000,
    test_weights={"accepts a valid move": 2.0, "ownership is checked": 2.0, "token bucket per seat": 2.0},
)

NODE_SEAT_RECONNECT = Task(
    id="node_seat_reconnect",
    difficulty=4,
    description=(
        "Implement createSeats in src/seats.js: seat ownership across disconnects for a Node.js match server. "
        "Sockets are opaque ids; now() and newToken() are injected; side effects are returned as events. "
        "Each team in options.teams is a seat in one of four states: free, live (bound to a socket), held "
        "(owner disconnected, waiting out the grace window) or ai (grace expired, AI playing it). Methods: "
        "join(socketId, name): alreadySeated if this socket owns a live seat; badName unless name is a "
        "string of 1..16 characters after trimming (store it trimmed); take the lowest-numbered free team, "
        "else the lowest-numbered ai team (adding event {type: 'aiRelease', team}), else full; held seats "
        "are never given to newcomers; returns {ok: true, team, token: newToken(), events}. "
        "reclaim(socketId, token): unknownToken unless token is a non-empty string matching a non-free "
        "seat's current token; alreadySeated if this socket owns a different live seat; otherwise the seat "
        "becomes live on this socket and returns {ok: true, team, name, events}, where events is "
        "[{type: 'close', socketId: oldSocket, code: 4000, reason: 'superseded'}] when another socket held "
        "it live, [{type: 'aiRelease', team}] when it was ai, else []. A newcomer taking an ai seat issues a "
        "new token, so the previous owner's token stops working. "
        "disconnect(socketId): if the socket owns a live seat it becomes held until now() + graceMs and "
        "returns {held: true, team, untilMs}; otherwise {held: false} (a superseded socket closing later "
        "must not affect the seat). sweep(): every held seat whose untilMs <= now() becomes ai, returning "
        "[{type: 'aiTakeover', team}] in team order (each seat once). leave(socketId): the socket's live "
        "seat becomes free (token retired), returning {left: true, team} or {left: false}. seats(): "
        "[{team, state, name}] in ascending team order, name null when free."
    ),
    subdir="node_seat_reconnect",
    editable_files=["src/seats.js"],
    context_files=["tests/seats.test.js", "package.json"],
    test_cmd=["node", "--test", "tests/seats.test.js"],
    test_timeout=60,
    num_ctx=24576,      # the 8192 default cut thinking models off mid-file (2026-10-08)
    min_predict=12000,
    test_weights={"reclaim within grace": 2.0, "newest socket wins": 2.0},
)

CROSSPLAY_STATEHASH_PARITY = Task(
    id="crossplay_statehash_parity",
    difficulty=5,
    description=(
        "Implement src/GameClient/StateHash.cs: a C# port of the Node.js server's read-only "
        "js/statehash.js, which is the specification. The Unity client hashes its own copy of the "
        "authoritative state and compares it with the hash the server publishes, so the port must match "
        "the JavaScript exactly for every input, byte for byte and value for value (the tests use "
        "fixtures generated by running the JavaScript). FixedMath.FloorDiv / TruncDiv / SampleCellX must "
        "return what floorDiv / truncDiv / sampleCellX return for every int32 argument, including negative "
        "values and int.MinValue (the JavaScript wraps results to int32 with |0). ByteWriter mirrors "
        "createByteWriter (methods U8, U16, U32, I32, Bool, OptU32, Str, ToBytes; little-endian; each "
        "returns the writer for chaining; out-of-range values throw ArgumentOutOfRangeException and a null "
        "string throws ArgumentNullException); Str must encode exactly as the JavaScript does, including "
        "strings that contain unpaired UTF-16 surrogates. StateHash.Fnv1a64 returns the 16-digit lowercase "
        "hex FNV-1a 64 hash; StateBytes writes the canonical layout from js/statehash.js without reordering "
        "the caller's Units list; HashState = Fnv1a64(StateBytes(state))." + UNITY_CONSTRAINTS
    ),
    subdir="crossplay_statehash_parity",
    editable_files=["src/GameClient/StateHash.cs"],
    context_files=[
        "js/statehash.js",
        "src/GameClient/GameState.cs",
        "tests/GameClientTests/StateHashParityTests.cs",
        "src/GameClient/GameClient.csproj",
    ],
    test_cmd=["dotnet", "test", "--verbosity", "normal"],
    test_timeout=180,
    setup_cmd=["dotnet", "restore"],
    setup_timeout=180,
    num_ctx=24576,
    min_predict=12000,
    test_weights={"StateBytes_Match": 3.0, "HashState_MatchesTheServerHash": 3.0, "RejectsOutOfRange": 0.5},
)

MULTIHOP_CHAIN_5 = Task(
    id="multihop_chain_5",
    difficulty=4,
    description=(
        "A configuration reference document is provided as context. "
        "It defines a hierarchy of named profiles; each profile may declare a 'parent' profile "
        "and can override any key from its ancestors. "
        "The effective value of a key for a profile is the first definition found "
        "walking from that profile up through its parent chain to the root. "
        "Find the effective value of 'retention_days' for the profile 'rtfd-prod-instance-07' "
        "and write that numeric value — and nothing else — to answer.txt."
    ),
    subdir="multihop_chain_5",
    editable_files=["answer.txt"],
    context_files=["documents/config_reference.txt"],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=8192,
    min_predict=8192,
)

MULTIHOP_CROSS_5 = Task(
    id="multihop_cross_5",
    difficulty=4,
    description=(
        "Five reference documents are provided as context: a Service Registry, "
        "a Team Directory, an Office Reference, a Criticality Classification, "
        "and an Escalation Policy. "
        "Use all five documents to determine the primary oncall contact for P1 incidents "
        "affecting the 'inventory-sync' service. "
        "Write that contact address — and nothing else — to answer.txt."
    ),
    subdir="multihop_cross_5",
    editable_files=["answer.txt"],
    context_files=[
        "documents/1_service_registry.txt",
        "documents/2_team_directory.txt",
        "documents/3_office_reference.txt",
        "documents/4_criticality.txt",
        "documents/5_escalation_policy.txt",
    ],
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
    test_timeout=15,
    num_ctx=8192,
    min_predict=8192,
)

BUILTIN_TASKS: list[Task] = [
    CSV_NORDIC_PROPERTY,
    NODE_SLUGIFY,
    PYTHON_SAFE_DIV,
    DOTNET_SAS,
    NODE_CSV_PARSER,
    PYTHON_LRU_CACHE,
    PYTHON_LFU_CACHE,
    PYTHON_MINHEAP,
    PYTHON_MULTIFILE_RENAME,
    NODE_MEMOIZE_BUG,
    PYTHON_LEDGER_BUG,
    PYTHON_EXPR_EVAL,
    PYTHON_DIJKSTRA,
    PYTHON_HASHMAP,
    PYTHON_TOKENIZER,
    NODE_DEBOUNCE,
    PYTHON_MERGE_INTERVALS,
    AWK_CSV_STATS,
    JAVA_WORD_FREQ,
    PYTHON_CONFIG_LOADER,
    BASH_PREFLIGHT,
    NODE_EXPRESS_VALIDATION,
    PYTHON_FASTAPI_ENDPOINT,
    CS_COORD_CONVERT,
    CS_COORD_BAM,
    CS_PORT_MOVEMENT,
    CS_PORT_HEIGHTMAP,
    CS_PORT_WEBAUDIO,
    CS_TICK_INTERP,
    CS_WS_ABORT_RECONNECT,
    CS_RECONNECT_POLICY,
    CS_WS_CLIENT,
    CS_PRIMITIVE_COMPOSE,
    CS_MAIN_THREAD_DISPATCH,
    CS_PROTOCOL_CODEC,
    CS_SNAPSHOT_INTERP,
    CS_PREDICT_RECONCILE,
    NODE_ROOM_AUTHORITY,
    NODE_SEAT_RECONNECT,
    CROSSPLAY_STATEHASH_PARITY,
    NODE_PARATROOPER,
    NODE_PARA_CORE,
    NODE_PARA_TURRET,
    NODE_PARA_ENTITIES,
    NODE_PARA_COMBAT,
    CONTEXT_8K,
    CONTEXT_16K,
    CONTEXT_32K,
    CONTEXT_64K,
    MULTIHOP_FORWARD,
    MULTIHOP_REVERSE,
    DISTRACTOR_NOTES,
    MULTIHOP_CHAIN_5,
    MULTIHOP_CROSS_5,
    CONTEXT_128K,
    CONTEXT_256K,
]
TASK_MAP: dict[str, Task] = {t.id: t for t in BUILTIN_TASKS}

# Predefined task groups for --task-group.  Each list preserves BUILTIN_TASKS order.
TASK_GROUPS: dict[str, list[str]] = {
    "coding": [
        "csv_nordic_property",
        "node_slugify", "python_safe_div", "dotnet_sas",
        "node_csv_parser",
        "python_lru_cache", "python_lfu_cache", "python_minheap",
        "python_multifile_rename", "node_memoize_bug",
        "python_ledger_bug", "python_expr_eval",
        "python_dijkstra", "python_hashmap", "python_tokenizer",
        "node_debounce", "python_merge_intervals", "awk_csv_stats", "java_word_freq",
    ],
    "l6": [
        "node_para_core", "node_para_turret", "node_para_entities", "node_para_combat",
    ],
    "para": [
        "node_para_core", "node_para_turret", "node_para_entities", "node_para_combat",
    ],
    "l6_full": [
        "node_paratrooper",
    ],
    "spot": [
        "python_safe_div", "node_slugify", "python_lru_cache", "csv_nordic_property",
        "node_csv_parser", "python_tokenizer", "python_expr_eval", "python_hashmap",
        "node_para_core", "node_paratrooper",
    ],
    "context": [
        "context_8k", "context_16k", "context_32k",
        "context_64k", "context_128k", "context_256k",
    ],
    "multihop": [
        "multihop_forward", "multihop_reverse", "distractor_notes",
        "multihop_chain_5", "multihop_cross_5",
    ],
    "web": [
        "python_config_loader",
        "bash_preflight",
        "node_express_validation",
        "python_fastapi_endpoint",
    ],
    "gamedev": [
        "cs_coord_convert", "cs_coord_bam", "cs_port_movement", "cs_port_heightmap", "cs_port_webaudio", "cs_tick_interp", "cs_ws_abort_reconnect", "cs_reconnect_policy", "cs_ws_client", "cs_primitive_compose", "cs_main_thread_dispatch", "cs_protocol_codec", "cs_snapshot_interp",
        "cs_predict_reconcile", "node_room_authority", "node_seat_reconnect",
        "crossplay_statehash_parity",
    ],
}

# Groups left out of a run with no --tasks/--task-group (and so out of compare.sh's default
# totals and Skill levels) until their difficulty levels are validated across models.
OPT_IN_GROUPS: tuple[str, ...] = ("gamedev",)
_OPT_IN_IDS = {tid for g in OPT_IN_GROUPS for tid in TASK_GROUPS[g]}
DEFAULT_TASKS: list[Task] = [t for t in BUILTIN_TASKS if t.id not in _OPT_IN_IDS]
