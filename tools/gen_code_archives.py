#!/usr/bin/env python3
"""Generate Python stdlib code archives for context_128k and context_256k tasks.

Archives are concatenated stdlib source files with a sentinel constant injected
at 50% depth. The sentinel's value is the answer the benchmark task expects.

Usage: python3 tools/gen_code_archives.py
"""

import sys
from pathlib import Path

STDLIB = Path("/usr/lib/python3.12")
REPO = Path(__file__).parent.parent

# Curated list of good stdlib files — real code, varied domains, no data tables
POOL_FILES = [
    "ast.py",
    "asyncio/base_events.py",
    "asyncio/selector_events.py",
    "asyncio/tasks.py",
    "asyncio/unix_events.py",
    "codecs.py",
    "collections/__init__.py",
    "concurrent/futures/process.py",
    "configparser.py",
    "dataclasses.py",
    "difflib.py",
    "email/message.py",
    "enum.py",
    "fractions.py",
    "functools.py",
    "http/client.py",
    "http/server.py",
    "importlib/_bootstrap_external.py",
    "ipaddress.py",
    "logging/__init__.py",
    "logging/config.py",
    "logging/handlers.py",
    "multiprocessing/connection.py",
    "os.py",
    "pathlib.py",
    "pickle.py",
    "platform.py",
    "re/_parser.py",
    "shutil.py",
    "smtplib.py",
    "socket.py",
    "ssl.py",
    "statistics.py",
    "subprocess.py",
    "tempfile.py",
    "threading.py",
    "traceback.py",
    "urllib/parse.py",
    "xml/etree/ElementTree.py",
    "zipfile/__init__.py",
    "_pyio.py",
]


def make_sentinel_block(value: str) -> str:
    return (
        "# ==============================\n"
        "# stdlib/internal/benchmark_config.py\n"
        "# Internal benchmark configuration — do not import directly.\n"
        "# ==============================\n"
        "\n"
        f'BENCHMARK_SENTINEL_VALUE = "{value}"\n'
        "_ARCHIVE_VERSION = 2\n"
        "_ARCHIVE_FORMAT = 'stdlib-concat'\n"
    )


def build_pool() -> list[tuple[str, str]]:
    entries = []
    for rel in POOL_FILES:
        p = STDLIB / rel
        if not p.exists():
            print(f"  WARN: missing {p}", file=sys.stderr)
            continue
        content = p.read_text(encoding="utf-8", errors="replace")
        header = f"# ==============================\n# stdlib/{rel}\n# ==============================\n\n"
        entries.append((rel, header + content + "\n"))
    return entries


def build_archive(entries: list[tuple[str, str]], target_bytes: int, sentinel_value: str) -> str:
    pool = "".join(text for _, text in entries)

    # Truncate pool to double the target so we can split at 50%
    half = target_bytes // 2
    first_half = pool[:half]
    second_half = pool[half : half * 2]

    sentinel = make_sentinel_block(sentinel_value)
    archive = (
        "# ==============================\n"
        "# Python Standard Library Source Archive\n"
        "# CPython 3.12 — selected modules\n"
        "# ==============================\n\n"
        + first_half
        + "\n" + sentinel + "\n"
        + second_half
    )
    return archive


def write_task(task_id: str, archive: str, sentinel_value: str) -> None:
    base = REPO / "task_data" / task_id
    (base / "documents").mkdir(parents=True, exist_ok=True)
    (base / "tests").mkdir(parents=True, exist_ok=True)

    (base / "documents" / "code_archive.py").write_text(archive, encoding="utf-8")

    (base / "answer.txt").write_text("RC-0000\n", encoding="utf-8")

    test_src = (
        "from pathlib import Path\n"
        "\n"
        "ANSWER_FILE = Path(__file__).parent.parent / \"answer.txt\"\n"
        f'EXPECTED = "{sentinel_value}"\n'
        "\n"
        "\n"
        "def test_sentinel_value():\n"
        "    text = ANSWER_FILE.read_text(encoding=\"utf-8\").strip()\n"
        "    assert text == EXPECTED, f\"Expected {EXPECTED!r}, got {text!r}\"\n"
    )
    (base / "tests" / "test_answer.py").write_text(test_src, encoding="utf-8")
    print(f"  {task_id}: {len(archive):,} bytes  sentinel={sentinel_value!r}")


def main() -> None:
    print("Building stdlib pool...")
    entries = build_pool()
    total = sum(len(t) for _, t in entries)
    print(f"  Pool: {len(entries)} files, {total:,} bytes")

    # 128k task: target ~440 KB archive (fills ~110k tokens at 4 chars/tok, within num_ctx=131072)
    TARGET_128K = 440_000
    # 256k task: target ~880 KB archive (fills ~220k tokens at 4 chars/tok, within num_ctx=262144)
    TARGET_256K = 880_000

    if total < TARGET_256K:
        print(f"ERROR: pool ({total:,} B) smaller than 256k target ({TARGET_256K:,} B)", file=sys.stderr)
        sys.exit(1)

    print("\nGenerating archives...")
    archive_128k = build_archive(entries, TARGET_128K, "RC-4471")
    archive_256k = build_archive(entries, TARGET_256K, "RC-8803")

    write_task("context_128k", archive_128k, "RC-4471")
    write_task("context_256k", archive_256k, "RC-8803")
    print("\nDone.")


if __name__ == "__main__":
    main()
