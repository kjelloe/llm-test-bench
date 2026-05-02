import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

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
    num_ctx: int | None = None      # override global --num-ctx for this task (None = use global)
    min_predict: int | None = None  # floor on --num-predict for this task; useful when the output
                                    # file is large and thinking models need extra token budget


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


def _run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = r.stdout + r.stderr
        # Keep the head (primary errors) and tail (summary) — both matter for cascading failures.
        if len(out) > 1200:
            out = out[:600] + "\n…(truncated)…\n" + out[-400:]
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return -1, f"Timed out after {timeout}s"


def run_setup(task: Task, workdir: Path) -> tuple[bool, str]:
    if not task.setup_cmd:
        return True, ""
    rc, out = _run(task.setup_cmd, workdir, task.setup_timeout)
    return rc == 0, out


def run_tests(task: Task, workdir: Path) -> tuple[bool, str]:
    rc, out = _run(task.test_cmd, workdir, task.test_timeout)
    return rc == 0, out


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
    min_predict=16384,  # ~350 tokens output; gpt-oss:20b burns ~13k tokens reasoning → 12800 hit ceiling, 16384 gives safe headroom
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
    min_predict=8192,  # ~630 tokens to output the full file; gpt-oss:20b burns ~5k tokens reasoning → 4800 hit ceiling, 8192 gives safe headroom
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
    min_predict=12800,
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
    min_predict=8192,
)

BUILTIN_TASKS: list[Task] = [
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
]
TASK_MAP: dict[str, Task] = {t.id: t for t in BUILTIN_TASKS}
