"""Guards for the game-dev task group. C# tasks carry their own copy of the UnityEngine shim
(task dirs must be self-contained for prepare_workdir/export_task); the copies must match the
canonical one. crossplay_statehash_parity's fixtures must be exactly what its JS spec produces."""
import shutil
import subprocess
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


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_statehash_fixtures_match_js_spec():
    task_dir = TASK_DATA_DIR / "crossplay_statehash_parity"
    out = subprocess.run(["node", "js/make-fixtures.js"], cwd=task_dir, capture_output=True, text=True, timeout=30, check=True)
    assert out.stdout == (task_dir / "tests" / "GameClientTests" / "fixtures.json").read_text(encoding="utf-8")
