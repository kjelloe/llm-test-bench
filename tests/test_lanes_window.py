"""lanes-window.sh against a stand-in llmctl and systemctl: waits for idle, stops, runs, always restarts."""
import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "lanes-window.sh"


def _exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(tmp_path: Path, active: bool, idle_after: int, cmd: list[str]) -> tuple[int, list[str]]:
    log = tmp_path / "log"
    count = tmp_path / "idle-calls"
    count.write_text("0")
    _exe(tmp_path / "llmctl", f"""echo "$@" >> {log}
case "$1" in
  units) echo llm-backend ;;
  idle) n=$(($(cat {count}) + 1)); echo $n > {count}; [ $n -gt {idle_after} ] ;;
esac
""")
    _exe(tmp_path / "systemctl", "exit 0\n" if active else "exit 3\n")
    env = {**os.environ, "LLMCTL": str(tmp_path / "llmctl"), "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    rc = subprocess.run([str(SCRIPT), "--idle", "30", "--poll", "0", "--", *cmd], env=env,
                        capture_output=True, text=True, timeout=30).returncode
    calls = log.read_text().splitlines() if log.exists() else []
    return rc, [c for c in calls if c != "units"]


def test_waits_for_idle_then_stops_runs_and_restarts(tmp_path):
    rc, calls = _run(tmp_path, active=True, idle_after=2, cmd=["true"])
    assert rc == 0
    assert calls == ["idle 30", "idle 30", "idle 30", "stop", "start"]


def test_restarts_even_when_the_command_fails(tmp_path):
    rc, calls = _run(tmp_path, active=True, idle_after=0, cmd=["sh", "-c", "exit 7"])
    assert rc == 7
    assert calls[-2:] == ["stop", "start"]


def test_leaves_a_stopped_backend_alone(tmp_path):
    rc, calls = _run(tmp_path, active=False, idle_after=0, cmd=["true"])
    assert rc == 0
    assert calls == []
