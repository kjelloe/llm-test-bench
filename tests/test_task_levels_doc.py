"""The task levels written in SPEC.md and in CLAUDE.md's task tables must match lib/tasks.py (re-levelled 2026-10-14)."""
import re
from pathlib import Path

import lib.tasks as T

ROOT = Path(__file__).resolve().parent.parent
LEVELS = {v.id: v.difficulty for v in vars(T).values() if isinstance(v, T.Task)}


def _mismatches(pairs):
    return [(tid, int(level), LEVELS[tid]) for tid, level in pairs if tid in LEVELS and int(level) != LEVELS[tid]]


def test_spec_levels_match_tasks():
    text = (ROOT / "SPEC.md").read_text()
    assert _mismatches(re.findall(r"`([a-z0-9_]+)` \(L(\d)", text)) == []


def test_claude_md_task_table_levels_match_tasks():
    rows = re.findall(r"^\| `([a-z0-9_]+)`(?: \[[^\]]+\])?(?: \([^)]*\))? \| (\d) \|", (ROOT / "CLAUDE.md").read_text(), re.M)
    assert rows, "task tables not found"
    assert _mismatches(rows) == []
