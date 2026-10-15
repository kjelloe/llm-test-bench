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


# Tasks whose UnityEngine.cs deliberately extends the canonical shim (kept out of the shared copy so the
# other tasks' prompts do not change): cs_fake_null adds Unity's object lifetime (Object, Destroy, PlayerLoop).
EXTENDED_SHIM = {"cs_fake_null"}


def test_shim_copies_match_canonical():
    tasks = _cs_gamedev_tasks()
    assert tasks
    for task in tasks:
        for name in SHIM_FILES:
            if task.id in EXTENDED_SHIM and name == "UnityEngine.cs":
                continue
            copy = TASK_DATA_DIR / task.subdir / "shim" / "UnityShim" / name
            assert copy.read_bytes() == (CANONICAL / name).read_bytes(), f"{task.id}: {name} differs from _shared"


def test_gamedev_tasks_have_reference_solution():
    for tid in TASK_GROUPS["gamedev"] + TASK_GROUPS["fastengine"]:
        task = TASK_MAP[tid]
        editable = Path(task.editable_files[0])
        reference = TASK_DATA_DIR / task.subdir / editable.with_name(editable.stem + ".reference" + editable.suffix)
        assert reference.is_file(), f"{task.id}: missing {reference.name}"


# (task dir, generator script, fixture path) — fixtures must be exactly what the real JS produces.
JS_FIXTURES = [
    ("crossplay_statehash_parity", "js/make-fixtures.js", "tests/GameClientTests/fixtures.json"),
    ("cs_port_movement", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
    ("cs_port_heightmap", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
    ("cs_port_qr", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
    ("cs_port_helm", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
    ("cs_interp_alloc_free", "js/make-fixtures.mjs", "tests/GameClientTests/fixtures.json"),
    ("fe_three_geometry", "js/make-fixtures.mjs", "tests/FastengineTests/fixtures.json"),
    ("fe_render_order", "js/make-fixtures.reference.mjs", "tests/FastengineTests/fixtures.json"),
    ("fe_object3d", "js/make-fixtures.reference.mjs", "tests/FastengineTests/fixtures.json"),
    ("fe_i18n", "js/make-fixtures.mjs", "tests/FastengineTests/fixtures.json"),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("task_dir,script,fixture", JS_FIXTURES)
def test_js_generated_fixtures_match_their_generator(task_dir, script, fixture):
    root = TASK_DATA_DIR / task_dir
    out = subprocess.run(["node", script], cwd=root, capture_output=True, text=True, timeout=60, check=True)
    assert out.stdout == (root / fixture).read_text(encoding="utf-8")


def test_gamedev_is_opt_in_for_default_runs():
    from lib.tasks import BUILTIN_TASKS, DEFAULT_TASKS, OPT_IN_GROUPS

    default_ids = {t.id for t in DEFAULT_TASKS}
    opt_in = {tid for g in OPT_IN_GROUPS for tid in TASK_GROUPS[g]}
    assert not default_ids & opt_in, "gamedev groups must not change default totals or Skill levels"
    assert len(DEFAULT_TASKS) == len(BUILTIN_TASKS) - len(opt_in)


DIAG_GROUPS = ["gamedev_diag", "fastengine_diag"]


@pytest.mark.parametrize("group", DIAG_GROUPS)
def test_diag_key_covers_every_question_and_matches_the_reference(group):
    import hashlib
    import json

    root = TASK_DATA_DIR / group
    key = json.loads((root / "tests" / "answer_key.json").read_text())
    reference = json.loads((root / "answers.reference.json").read_text())
    qids = {TASK_MAP[t].editable_files[0].split("/")[1][:-4] for t in TASK_GROUPS[group]}
    assert qids == set(key) == set(reference)
    for qid in qids:
        assert (root / "questions" / f"{qid}.md").is_file()
        assert (root / "answers" / f"{qid}.txt").read_text().strip() == "?", f"{qid}: the stub must not answer"
        assert hashlib.sha256(f"{group}:{qid}:{reference[qid]['answer']}".encode()).hexdigest() == key[qid]


def test_every_test_weight_key_names_a_real_test():
    for tid in TASK_GROUPS["gamedev"] + TASK_GROUPS["fastengine"]:
        task = TASK_MAP[tid]
        test_files = [f for f in task.context_files if "test" in Path(f).name.lower()]
        text = "".join((TASK_DATA_DIR / task.subdir / f).read_text(encoding="utf-8") for f in test_files)
        for key in task.test_weights or {}:
            assert key in text, f"{tid}: weight key {key!r} matches no test in {test_files}"


def test_context_fits_prompt_plus_thinking_budget():
    # Longest measured gamedev prompt: ~9.3k tokens (cs_predict_reconcile, 2026-10-08). The node
    # tasks once ran at the 8192 default and cut thinking models off mid-file.
    for tid in TASK_GROUPS["gamedev"] + TASK_GROUPS["fastengine"]:
        task = TASK_MAP[tid]
        assert task.num_ctx and task.num_ctx >= task.min_predict + 9500, tid


@pytest.mark.parametrize("group", DIAG_GROUPS)
def test_diag_generator_reproduces_the_committed_files(tmp_path, group):
    root = TASK_DATA_DIR / group
    subprocess.run([sys.executable, str(root / "make_diag.reference.py"), str(tmp_path)],
                   check=True, capture_output=True, timeout=60)
    for rel in ["tests/answer_key.json", "answers.reference.json",
                *[str(p.relative_to(root)) for p in sorted((root / "questions").glob("*.md"))],
                *[str(p.relative_to(root)) for p in sorted((root / "answers").glob("*.txt"))]]:
        assert (tmp_path / rel).read_bytes() == (root / rel).read_bytes(), f"{rel} differs from make_diag.reference.py output"


def test_extended_shims_keep_every_canonical_type():
    canonical = (CANONICAL / "UnityEngine.cs").read_text()
    import re
    types = set(re.findall(r"public (?:static |sealed |readonly )*(?:class|struct|enum) (\w+)", canonical))
    for tid in EXTENDED_SHIM:
        text = (TASK_DATA_DIR / TASK_MAP[tid].subdir / "shim" / "UnityShim" / "UnityEngine.cs").read_text()
        missing = types - set(re.findall(r"public (?:static |sealed |readonly )*(?:class|struct|enum) (\w+)", text))
        assert not missing, f"{tid}: extended shim lost {sorted(missing)}"


# Fixtures generated by a Python reader (independent of the C# reference) must match their generator.
PY_FIXTURES = [("fe_ttf_metrics", "make_fixtures.reference.py", "tests/FastengineTests/fixtures.json")]


@pytest.mark.parametrize("task_dir,script,fixture", PY_FIXTURES)
def test_python_generated_fixtures_match_their_generator(task_dir, script, fixture):
    root = TASK_DATA_DIR / task_dir
    out = subprocess.run([sys.executable, script], cwd=root, capture_output=True, text=True, timeout=60, check=True)
    assert out.stdout == (root / fixture).read_text(encoding="utf-8")


# fe_flex_wrap's fixtures are Chromium's layout (Playwright); regenerate them where Playwright is installed.
_PLAYWRIGHT = Path.home() / "GIT" / "boombrawl" / "node_modules" / "playwright-core"


@pytest.mark.skipif(shutil.which("node") is None or not _PLAYWRIGHT.is_dir(), reason="node or Playwright not available")
def test_flex_fixtures_match_chromium():
    import os
    root = TASK_DATA_DIR / "fe_flex_wrap"
    out = subprocess.run(["node", "tools/make_fixtures.reference.mjs"], cwd=root, capture_output=True, text=True,
                         timeout=180, check=True, env={**os.environ, "PLAYWRIGHT": str(_PLAYWRIGHT)})
    assert out.stdout == (root / "tests" / "FastengineTests" / "fixtures.json").read_text(encoding="utf-8")


# fe_output_color's fixtures are pixels three r162 rendered in Chromium (Playwright, SwiftShader WebGL).
@pytest.mark.skipif(shutil.which("node") is None or not _PLAYWRIGHT.is_dir(), reason="node or Playwright not available")
def test_output_color_fixtures_match_three_in_chromium():
    import os
    root = TASK_DATA_DIR / "fe_output_color"
    out = subprocess.run(["node", "tools/make_fixtures.reference.mjs"], cwd=root, capture_output=True, text=True,
                         timeout=300, check=True, env={**os.environ, "PLAYWRIGHT": str(_PLAYWRIGHT)})
    assert out.stdout == (root / "tests" / "FastengineTests" / "fixtures.json").read_text(encoding="utf-8")


def test_every_fixture_generator_is_guarded():
    """A task whose fixtures come from a generator must have that generator in one of the guards above."""
    guarded = {(t, s) for t, s, _ in JS_FIXTURES} | {(t, s) for t, s, _ in PY_FIXTURES}
    guarded |= {("fe_flex_wrap", "tools/make_fixtures.reference.mjs"), ("fe_output_color", "tools/make_fixtures.reference.mjs")}
    found = set()
    for path in TASK_DATA_DIR.glob("*/**/make[-_]fixtures*"):
        rel = path.relative_to(TASK_DATA_DIR)
        found.add((rel.parts[0], "/".join(rel.parts[1:])))
    assert found <= guarded, f"unguarded fixture generators: {sorted(found - guarded)}"


def test_fastengine_tasks_target_what_fastengine_targets():
    """fastengine moved to .NET 10 (net10.0) on 2026-10-14; its tasks follow it, the Unity ones stay netstandard2.1/net9.0."""
    for tid in TASK_GROUPS["fastengine"]:
        for proj in (TASK_DATA_DIR / TASK_MAP[tid].subdir).rglob("*.csproj"):
            assert "<TargetFramework>net10.0</TargetFramework>" in proj.read_text(), f"{proj} is not net10.0"
