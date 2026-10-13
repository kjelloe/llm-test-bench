"""Drives scripts/job.sh against a throwaway bare repo whose commits build different zips."""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "job.sh"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30,
                          env={**os.environ, **GIT_ENV}, check=True).stdout.strip()


BUILD = """#!/usr/bin/env bash
set -e
mkdir -p dist
echo "building {name} in $PWD"
{body}
"""


@pytest.fixture
def lab(tmp_path):
    """SOURCE/game.git with commits A, B (build game-A.zip, game-B.zip) and BROKEN (build.sh fails)."""
    work = tmp_path / "game"
    work.mkdir()
    git(work, "init", "-q")
    commits = {}
    for name, body in [("A", 'echo A > dist/game-A.zip'), ("B", 'echo B > dist/game-B.zip'), ("BROKEN", 'echo half > dist/game-broken.zip; exit 3')]:
        (work / "build.sh").write_text(BUILD.format(name=name, body=body))
        (work / "build.sh").chmod(0o755)
        git(work, "add", "build.sh")
        git(work, "commit", "-q", "-m", name)
        commits[name] = git(work, "rev-parse", "HEAD")
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(source / "game.git")], check=True, timeout=30,
                   env={**os.environ, **GIT_ENV})
    lane = tmp_path / "lane" / "out"
    lane.mkdir(parents=True)
    return {"tmp": tmp_path, "source": source, "out": lane, "cache": tmp_path / "cache", "commits": commits}


def run(lab, *args, run_id="r1", env=None):
    e = {**os.environ, **GIT_ENV, "SOURCE": str(lab["source"]), "AW_OUT": str(lab["out"]), "AW_RUN_ID": run_id,
         "XDG_CACHE_HOME": str(lab["cache"])}
    e.update(env or {})
    r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=60, env=e,
                       cwd=lab["tmp"])
    log = lab["out"] / "build.log"
    last, deadline = None, time.time() + 3  # the log's tee may still be writing when the job exits
    while time.time() < deadline:
        now = log.read_text() if log.exists() else None
        if now == last:
            break
        last = now
        time.sleep(0.15)
    return r


def out_names(lab):
    return sorted(p.name for p in lab["out"].iterdir())


def manifest(lab):
    return json.loads((lab["out"] / "manifest.json").read_text())["files"]


def test_a_build_leaves_exactly_its_outputs(lab):
    r = run(lab, "game", lab["commits"]["A"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert out_names(lab) == ["build.log", "game-A.zip", "manifest.json"]
    data = (lab["out"] / "game-A.zip").read_bytes()
    assert manifest(lab) == [{"name": "game-A.zip", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]
    assert "building A" in (lab["out"] / "build.log").read_text()


def test_work_happens_outside_the_tree_and_is_removed(lab):
    assert run(lab, "game", lab["commits"]["A"], run_id="r7").returncode == 0
    jobs = lab["cache"] / "fastengine" / "jobs"
    assert not (jobs / "r7").exists(), "the run's work folder was left behind"
    assert all(p.is_file() for p in lab["out"].iterdir()), f"folders in the output: {out_names(lab)}"
    built_in = (lab["out"] / "build.log").read_text().split("building A in ", 1)[1].splitlines()[0]
    lane = str(lab["out"].parent)
    assert not built_in.startswith(lane), f"built inside the lane's tree ({built_in}); the manifest would see it"


def test_a_second_run_in_the_same_lane_starts_clean(lab):
    assert run(lab, "game", lab["commits"]["A"], run_id="r1").returncode == 0
    r = run(lab, "game", lab["commits"]["B"], run_id="r2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert out_names(lab) == ["build.log", "game-B.zip", "manifest.json"]
    assert [f["name"] for f in manifest(lab)] == ["game-B.zip"]
    log = (lab["out"] / "build.log").read_text()
    assert "building B" in log and "building A" not in log, "build.log still holds the earlier run"


def test_a_missing_commit_builds_nothing(lab):
    assert run(lab, "game", lab["commits"]["A"], run_id="r1").returncode == 0
    r = run(lab, "game", "0123456789abcdef0123456789abcdef01234567", run_id="r2")
    assert r.returncode == 1, (r.returncode, r.stdout + r.stderr)
    assert not any(n.endswith(".zip") for n in out_names(lab)), f"zips after a failed run: {out_names(lab)}"
    assert "0123456789abcdef" in (lab["out"] / "build.log").read_text() + r.stderr


def test_a_missing_source_repo_is_an_environment_error(lab):
    assert run(lab, "game", lab["commits"]["A"], run_id="r1").returncode == 0
    r = run(lab, "nosuchgame", lab["commits"]["A"], run_id="r2")
    assert r.returncode == 4, (r.returncode, r.stdout + r.stderr)
    assert not any(n.endswith(".zip") for n in out_names(lab)), f"zips after a failed run: {out_names(lab)}"


def test_a_failing_build_exits_1_without_zips(lab):
    r = run(lab, "game", lab["commits"]["BROKEN"])
    assert r.returncode == 1, (r.returncode, r.stdout + r.stderr)
    assert not any(n.endswith(".zip") for n in out_names(lab))
    assert "building BROKEN" in (lab["out"] / "build.log").read_text()


def test_unset_job_variables_are_an_environment_error(lab):
    r = run(lab, "game", lab["commits"]["A"], env={"AW_RUN_ID": ""})
    assert r.returncode == 4, (r.returncode, r.stdout + r.stderr)
