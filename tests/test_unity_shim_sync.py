"""Guards for the game-dev task group. C# tasks carry their own copy of the UnityEngine shim
(task dirs must be self-contained for prepare_workdir/export_task); the copies must match the
canonical one. crossplay_statehash_parity's fixtures must be exactly what its JS spec produces."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib.tasks import TASK_DATA_DIR, TASK_GROUPS, TASK_MAP

CANONICAL = TASK_DATA_DIR / "_shared" / "UnityShim"
SHIM_FILES = ["UnityEngine.cs", "UnityShim.csproj"]


def _cs_gamedev_tasks():
    return [TASK_MAP[t] for t in TASK_GROUPS["gamedev"] if (TASK_DATA_DIR / TASK_MAP[t].subdir / "shim").is_dir()]


def test_shim_copies_match_canonical():
    tasks = _cs_gamedev_tasks()
    assert tasks
    for task in tasks:
        for name in SHIM_FILES:
            copy = TASK_DATA_DIR / task.subdir / "shim" / "UnityShim" / name
            assert copy.read_bytes() == (CANONICAL / name).read_bytes(), f"{task.id}: {name} differs from _shared"


def test_gamedev_tasks_have_reference_solution():
    for tid in TASK_GROUPS["gamedev"]:
        task = TASK_MAP[tid]
        editable = Path(task.editable_files[0])
        reference = TASK_DATA_DIR / task.subdir / editable.with_name(editable.stem + ".reference" + editable.suffix)
        assert reference.is_file(), f"{task.id}: missing {reference.name}"


# (task dir, generator script, fixture path) — fixtures must be exactly what the real JS produces.
JS_FIXTURES = [
    ("crossplay_statehash_parity", "js/make-fixtures.js", "tests/GameClientTests/fixtures.json"),
    ("cs_port_movement", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
    ("cs_port_heightmap", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("task_dir,script,fixture", JS_FIXTURES)
def test_js_generated_fixtures_match_their_generator(task_dir, script, fixture):
    root = TASK_DATA_DIR / task_dir
    out = subprocess.run(["node", script], cwd=root, capture_output=True, text=True, timeout=60, check=True)
    assert out.stdout == (root / fixture).read_text(encoding="utf-8")


def test_gamedev_is_opt_in_for_default_runs():
    from lib.tasks import BUILTIN_TASKS, DEFAULT_TASKS

    default_ids = {t.id for t in DEFAULT_TASKS}
    opt_in = set(TASK_GROUPS["gamedev"]) | set(TASK_GROUPS["gamedev_diag"])
    assert not default_ids & opt_in, "gamedev groups must not change default totals or Skill levels"
    assert len(DEFAULT_TASKS) == len(BUILTIN_TASKS) - len(opt_in)


def test_diag_key_covers_every_question_and_matches_the_reference():
    import hashlib
    import json

    root = TASK_DATA_DIR / "gamedev_diag"
    key = json.loads((root / "tests" / "answer_key.json").read_text())
    reference = json.loads((root / "answers.reference.json").read_text())
    qids = {TASK_MAP[t].editable_files[0].split("/")[1][:-4] for t in TASK_GROUPS["gamedev_diag"]}
    assert qids == set(key) == set(reference)
    for qid in qids:
        assert (root / "questions" / f"{qid}.md").is_file()
        assert (root / "answers" / f"{qid}.txt").read_text().strip() == "?", f"{qid}: the stub must not answer"
        assert hashlib.sha256(f"gamedev_diag:{qid}:{reference[qid]['answer']}".encode()).hexdigest() == key[qid]


def test_every_test_weight_key_names_a_real_test():
    for tid in TASK_GROUPS["gamedev"]:
        task = TASK_MAP[tid]
        test_files = [f for f in task.context_files if "test" in Path(f).name.lower()]
        text = "".join((TASK_DATA_DIR / task.subdir / f).read_text(encoding="utf-8") for f in test_files)
        for key in task.test_weights or {}:
            assert key in text, f"{tid}: weight key {key!r} matches no test in {test_files}"


def test_context_fits_prompt_plus_thinking_budget():
    # Longest measured gamedev prompt: ~9.3k tokens (cs_predict_reconcile, 2026-10-08). The node
    # tasks once ran at the 8192 default and cut thinking models off mid-file.
    for tid in TASK_GROUPS["gamedev"]:
        task = TASK_MAP[tid]
        assert task.num_ctx and task.num_ctx >= task.min_predict + 9500, tid


def test_diag_generator_reproduces_the_committed_files(tmp_path):
    root = TASK_DATA_DIR / "gamedev_diag"
    subprocess.run([sys.executable, str(root / "make_diag.reference.py"), str(tmp_path)],
                   check=True, capture_output=True, timeout=60)
    for rel in ["tests/answer_key.json", "answers.reference.json",
                *[str(p.relative_to(root)) for p in sorted((root / "questions").glob("*.md"))],
                *[str(p.relative_to(root)) for p in sorted((root / "answers").glob("*.txt"))]]:
        assert (tmp_path / rel).read_bytes() == (root / rel).read_bytes(), f"{rel} differs from make_diag.reference.py output"
