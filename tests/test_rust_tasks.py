"""The `rust` group (bj-engine tasks): each task's reference passes end to end through run_one while the untouched
stub fails its baseline, partial credit comes from cargo's per-test lines, and the group stays opt-in."""
import shutil
from pathlib import Path

import pytest

from bench import run_one
from lib.ollama_client import OllamaMetrics, OllamaResponse
from lib.tasks import DEFAULT_TASKS, TASK_DATA_DIR, TASK_GROUPS, TASK_MAP
from lib.test_results import build_errors, parse_counts, score_output

RUST = TASK_GROUPS["rust"]
needs_cargo = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")


def _answer(task) -> str:
    rel = task.editable_files[0]
    ref = TASK_DATA_DIR / task.subdir / Path(rel).with_name(Path(rel).stem + ".reference" + Path(rel).suffix)
    return f"BEGIN_FILE {rel}\n{ref.read_text()}END_FILE\n"


def _chat(text: str):
    def chat_fn(**kwargs):
        n = sum(len(m.get("content", "")) for m in kwargs.get("messages", []))
        m = OllamaMetrics(prompt_eval_count=max(500, n // 4), eval_count=100, eval_duration=1_000_000_000)
        return OllamaResponse(content=text, thinking="", metrics=m)
    return chat_fn


def test_rust_group_is_opt_in_and_needs_cargo():
    assert len(RUST) == 10
    assert not {t.id for t in DEFAULT_TASKS} & set(RUST)
    for tid in RUST:
        task = TASK_MAP[tid]
        assert task.requires == ("cargo",)
        assert task.test_cmd[:3] == ["cargo", "test", "--offline"]
        assert (TASK_DATA_DIR / task.subdir / "Cargo.toml").is_file()
        assert not (TASK_DATA_DIR / task.subdir / "target").exists(), "a local cargo run left target/ in task_data"
        for rel in task.editable_files + task.context_files:
            assert (TASK_DATA_DIR / task.subdir / rel).is_file(), f"{tid}: {rel}"


@needs_cargo
@pytest.mark.parametrize("tid", RUST)
def test_reference_passes_end_to_end_and_the_stub_fails(tid):
    task = TASK_MAP[tid]
    rec = run_one(model="mock", task=task, client_url="http://unused", num_ctx=task.num_ctx or 8192, temperature=0.0,
                  seed=1, num_predict=400, model_timeout=60, chat_fn=_chat(_answer(task)))
    assert rec["baseline_failed"] is True, f"{tid}: the stub must fail"
    assert rec["tests_pass"] is True, f"{tid}: {str(rec.get('error_detail'))[-1500:]}"
    assert rec["test_score"]["score"] == 1.0 and rec["test_score"]["total"] >= 7


CARGO_OUTPUT = """
running 3 tests
test bayer_2 ... ok
test bayer_4 ... FAILED
test other_sizes_panic - should panic ... ok

failures:
test result: FAILED. 2 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
"""


def test_cargo_per_test_lines_give_partial_credit():
    s = score_output(CARGO_OUTPUT)
    assert (s["passed"], s["total"], s["weighted"]) == (2, 3, True)
    assert s["failed"] == ["bayer_4"]


def test_cargo_summary_lines_are_summed_over_test_binaries():
    out = ("test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured\n"
           "test result: FAILED. 5 passed; 2 failed; 0 ignored; 0 measured\n")
    assert parse_counts(out) == (5, 7)


def test_rustc_errors_count_as_build_errors():
    out = ("error[E0308]: mismatched types\n  --> src/fixed.rs:12:5\n   |\n"
           "error[E0425]: cannot find value `x` in this scope\n  --> src/fixed.rs:20:9\n")
    b = build_errors(out)
    assert b["errors"] == 2 and b["codes"] == {"E0308": 1, "E0425": 1} and b["unity"] == []


# (task, generator, what it needs) — each generator writes fixtures/ and must reproduce it byte for byte.
RUST_FIXTURES = [
    ("rs_fixed_movement", "tools/make_fixtures.reference.mjs", "node"),
    ("rs_audio_ramps", "tools/make_fixtures.reference.mjs", "playwright"),
    ("rs_burst_drain", "tools/make_fixtures.reference.py", "bj-engine"),
    ("rs_pick_sea", "tools/make_fixtures.reference.py", "bj-engine:commander.json"),
]
_PLAYWRIGHT = Path.home() / "GIT" / "boombrawl" / "node_modules" / "playwright-core"
_BJ = Path.home() / "GIT" / "bj-engine"
BJ_COMMIT = "60a8097"  # the bj-engine commit rs_burst_drain's frames were taken from


def _regenerate(task: str, script: str, need: str, tmp: Path) -> Path:
    import os
    import subprocess
    work = tmp / task
    shutil.copytree(TASK_DATA_DIR / task, work)
    shutil.rmtree(work / "fixtures")
    (work / "fixtures").mkdir()
    if need.startswith("bj-engine"):
        name = need.partition(":")[2] or "fixture.json"
        src = tmp / name
        src.write_bytes(subprocess.run(["git", "-C", str(_BJ), "show", f"{BJ_COMMIT}:games/carrierdominion/Tests/{name}"],
                                       capture_output=True, check=True, timeout=60).stdout)
        cmd = ["python3", script, str(src)]
    else:
        cmd = ["node", script]
    env = {**os.environ, "PLAYWRIGHT": str(_PLAYWRIGHT)}
    subprocess.run(cmd, cwd=work, check=True, timeout=300, env=env, capture_output=True)
    return work / "fixtures"


def _available(need: str) -> bool:
    if need.startswith("bj-engine"):
        return (_BJ / ".git").exists() and shutil.which("git") is not None
    return shutil.which("node") is not None and (need != "playwright" or _PLAYWRIGHT.is_dir())


@pytest.mark.parametrize("task,script,need", RUST_FIXTURES)
def test_rust_fixtures_match_their_generator(task, script, need, tmp_path):
    if not _available(need):
        pytest.skip(f"{need} not available")
    fresh = _regenerate(task, script, need, tmp_path)
    kept = TASK_DATA_DIR / task / "fixtures"
    assert sorted(p.name for p in fresh.iterdir()) == sorted(p.name for p in kept.iterdir())
    for p in kept.iterdir():
        assert (fresh / p.name).read_bytes() == p.read_bytes(), f"{task}: fixtures/{p.name} differs from its generator"
