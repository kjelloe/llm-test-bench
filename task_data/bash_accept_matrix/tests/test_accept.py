"""Runs scripts/accept.sh in a scratch repo whose build/smoke/test scripts are fakes.

The fakes record every call in calls.log and fail on demand: FAIL_BUILD, FAIL_SMOKE and
FAIL_PLAY hold space-separated "game:target" pairs, FAIL_TEST=1 fails scripts/test.sh.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
GAMES = {"boombrawl": True, "carrierdominion": True, "fireline": False}  # game -> has PLAY_ARGS

FAKE = """#!/usr/bin/env bash
echo "{name} $*" >> calls.log
echo "noise from {name} on stdout"; echo "noise from {name} on stderr" >&2
pair="$1:$2"
case "{name}:$3" in
  build.sh:) [[ " $FAIL_BUILD " == *" $pair "* ]] && exit 2 ;;
  smoke.sh:) [[ " $FAIL_SMOKE " == *" $pair "* ]] && exit 3 ;;
  smoke.sh:play) [[ " $FAIL_PLAY " == *" $pair "* ]] && exit 4 ;;
  test.sh:) [[ -n $FAIL_TEST ]] && exit 1 ;;
esac
exit 0
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "scripts").mkdir()
    for name in ("accept.sh", "common.sh"):
        shutil.copy(TASK / "scripts" / name, tmp_path / "scripts" / name)
    for name in ("build.sh", "smoke.sh", "test.sh"):
        path = tmp_path / "scripts" / name
        path.write_text(FAKE.replace("{name}", name))
        path.chmod(0o755)
    for game, play in GAMES.items():
        (tmp_path / "games" / game).mkdir(parents=True)
        (tmp_path / "games" / game / "smoke.env").write_text("SMOKE_SECONDS=8\n" + ("PLAY_ARGS='-input \"1 w\"'\n" if play else ""))
    return tmp_path


def run(repo, *args, **fail):
    env = {**os.environ, "ACCEPT_NO_DOCKER": "1", "FAIL_BUILD": "", "FAIL_SMOKE": "", "FAIL_PLAY": "", "FAIL_TEST": ""}
    env.update({k: v for k, v in fail.items()})
    p = subprocess.run(["bash", "scripts/accept.sh", *args], cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    calls = (repo / "calls.log").read_text().splitlines() if (repo / "calls.log").exists() else []
    return p, calls


def lines(*rows):
    return [f"{g} {t}: {r}" for g, t, r in rows]


def test_all_pass_one_line_per_game_and_target_exit_zero(repo):
    p, _ = run(repo)
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == lines(*[(g, t, "pass") for g in sorted(GAMES) for t in ("linux64", "win64")])


def test_build_failure_is_reported_and_everything_else_still_runs(repo):
    p, calls = run(repo, FAIL_BUILD="boombrawl:linux64")
    assert p.returncode != 0
    out = p.stdout.splitlines()
    assert out[0] == "boombrawl linux64: BUILD FAIL (games/boombrawl/Build/linux64.log)"
    assert out[1:] == lines(("boombrawl", "win64", "pass"), ("carrierdominion", "linux64", "pass"),
                            ("carrierdominion", "win64", "pass"), ("fireline", "linux64", "pass"), ("fireline", "win64", "pass"))
    assert "smoke.sh boombrawl linux64" not in calls, "smoke ran after its build failed"


def test_smoke_failure_skips_play_and_continues(repo):
    p, calls = run(repo, FAIL_SMOKE="carrierdominion:win64")
    assert p.returncode != 0
    assert "carrierdominion win64: SMOKE FAIL (games/carrierdominion/Build/smoke-win64-player.log)" in p.stdout.splitlines()
    assert "smoke.sh carrierdominion win64 play" not in calls
    assert len(p.stdout.splitlines()) == 6


def test_play_runs_only_where_smoke_env_has_play_args(repo):
    p, calls = run(repo, FAIL_PLAY="boombrawl:win64")
    assert p.returncode != 0
    assert "boombrawl win64: PLAY FAIL (games/boombrawl/Build/play-win64-player.log)" in p.stdout.splitlines()
    assert not any(c.startswith("smoke.sh fireline") and c.endswith("play") for c in calls)
    assert "smoke.sh carrierdominion linux64 play" in calls


def test_several_failures_all_reported(repo):
    p, _ = run(repo, FAIL_BUILD="fireline:win64", FAIL_SMOKE="boombrawl:linux64", FAIL_PLAY="carrierdominion:linux64")
    assert p.returncode != 0
    out = p.stdout.splitlines()
    assert len(out) == 6
    assert sum(1 for l in out if l.endswith(": pass")) == 3


def test_named_games_only(repo):
    p, calls = run(repo, "fireline")
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == lines(("fireline", "linux64", "pass"), ("fireline", "win64", "pass"))
    assert not any("boombrawl" in c for c in calls)


def test_unit_test_failure_stops_before_any_build(repo):
    p, calls = run(repo, FAIL_TEST="1")
    assert p.returncode != 0
    assert p.stdout == ""
    assert "test.sh failed" in p.stderr
    assert not any(c.startswith("build.sh") for c in calls)


def test_tool_output_never_reaches_stdout(repo):
    p, _ = run(repo, FAIL_SMOKE="fireline:linux64")
    assert "noise" not in p.stdout
