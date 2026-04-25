import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

TASK_DATA_DIR = Path(__file__).parent / "task_data"


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

BUILTIN_TASKS: list[Task] = [NODE_SLUGIFY, PYTHON_SAFE_DIV, DOTNET_SAS, NODE_CSV_PARSER, PYTHON_LRU_CACHE]
TASK_MAP: dict[str, Task] = {t.id: t for t in BUILTIN_TASKS}
