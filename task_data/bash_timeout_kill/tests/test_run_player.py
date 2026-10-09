"""scripts/run_player.sh against fake players. Every run is wrapped in its own session with a
hard outer limit, so a broken script cannot hang the test run or leave players behind."""
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
PLAYERS = TASK / "tests" / "players"


def kill_session(sid):
    # timeout may move itself and the player into their own process group, so kill by session.
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError, IndexError):
            continue
        if int(fields[3]) == sid:
            try:
                os.kill(int(stat.parent.name), signal.SIGKILL)
            except ProcessLookupError:
                pass


def run(*args, limit=20):
    start = time.monotonic()
    p = subprocess.Popen(["bash", str(TASK / "scripts" / "run_player.sh"), *map(str, args)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        kill_session(p.pid)
        p.communicate()
        pytest.fail(f"run_player.sh still running after {limit}s")
    finally:
        kill_session(p.pid)
    return p.returncode, out, err, time.monotonic() - start


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except FileNotFoundError:
        return False


def test_a_player_that_ignores_sigterm_is_killed_five_seconds_later(tmp_path):
    pidfile = tmp_path / "pid"
    status, _, err, elapsed = run(1, PLAYERS / "stubborn.sh", pidfile)
    assert status == 124
    assert "timed out after 1s" in err
    assert 5.5 <= elapsed <= 8.5, f"took {elapsed:.1f}s; expected SIGTERM at 1s and SIGKILL 5s later"
    assert not alive(int(pidfile.read_text())), "the stubborn player is still running"


def test_a_well_behaved_player_gets_sigterm_first(tmp_path):
    marker = tmp_path / "marker"
    status, _, err, elapsed = run(1, PLAYERS / "graceful.sh", marker)
    assert marker.read_text().strip() == "graceful", "the player never got SIGTERM"
    assert status == 124
    assert "timed out after 1s" in err
    assert elapsed < 3


@pytest.mark.parametrize("code", [0, 3, 1])
def test_a_player_that_exits_keeps_its_status_and_output(code):
    status, out, err, elapsed = run(5, PLAYERS / "quick.sh", code)
    assert status == code
    assert out == "player output line\n"
    assert "timed out" not in err
    assert elapsed < 3


def test_arguments_with_spaces_reach_the_player(tmp_path):
    marker = tmp_path / "with space"
    status, _, _, _ = run(1, PLAYERS / "graceful.sh", marker)
    assert status == 124
    assert marker.read_text().strip() == "graceful"
