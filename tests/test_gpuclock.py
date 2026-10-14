"""gpuclock.sh: the commands it prints and its locked/unlocked verdict, against a stand-in nvidia-smi (never the real
cards: --print and status only read)."""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FAKE = """#!/bin/sh
case "$*" in
  *clocks.max.memory*) printf '0, 10501\\n1, 9751\\n2, 9751\\n' ;;
  *clocks.gr*) printf '0, %s, 810, P5\\n1, 1500, 810, P5\\n2, 1500, 405, P8\\n' "${FAKE_GPU0_CORE:-1500}" ;;
esac
"""


def run(tmp_path, *args, **env):
    (tmp_path / "nvidia-smi").write_text(FAKE)
    (tmp_path / "nvidia-smi").chmod(0o755)
    e = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", **env}
    return subprocess.run(["bash", str(REPO_ROOT / "gpuclock.sh"), *args], capture_output=True, text=True, timeout=30, env=e)


def test_wsl_lock_prints_core_and_per_card_memory_commands(tmp_path):
    r = run(tmp_path, "lock", "--memory", "--print", GPUCLOCK_WSL="1")
    assert r.returncode == 0, r.stderr
    for cmd in ["nvidia-smi -lgc 1500,2500", "nvidia-smi -i 0 -lmc 10501,10501", "nvidia-smi -i 2 -lmc 9751,9751"]:
        assert cmd in r.stdout
    line = next(l for l in r.stdout.splitlines() if "Start-Process" in l).strip()
    assert line.startswith('powershell.exe -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait')
    inner = line[len('powershell.exe -NoProfile -Command "'):-1]
    assert '"' not in inner, "a double quote inside the PowerShell argument breaks the outer shell's quoting"


def test_unlock_without_memory_only_resets_the_core(tmp_path):
    r = run(tmp_path, "unlock", "--print", GPUCLOCK_WSL="1")
    assert "nvidia-smi -rgc" in r.stdout and "-rmc" not in r.stdout


def test_native_linux_prints_sudo_commands(tmp_path):
    r = run(tmp_path, "lock", "--print", GPUCLOCK_WSL="0")
    assert r.stdout.strip() == "sudo nvidia-smi -lgc 1500,2500"


def test_status_flags_an_unlocked_gpu(tmp_path):
    assert run(tmp_path, "status").returncode == 0
    r = run(tmp_path, "status", FAKE_GPU0_CORE="210")
    assert r.returncode == 1 and "GPU0  core 210 MHz" in r.stdout and "NOT locked" in r.stdout


def test_run_sh_wires_the_clock_lock():
    """run.sh keeps --lock-clocks out of bench.py's arguments and asks gpuclock.sh before multi-GPU runs."""
    text = (REPO_ROOT / "run.sh").read_text()
    assert '"$_arg" == "--lock-clocks"' in text and "BENCH_LOCK_CLOCKS=auto" in text
    assert '"$_SCRIPT_DIR/gpuclock.sh" status' in text and '"$_SCRIPT_DIR/gpuclock.sh" lock' in text
