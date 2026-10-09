"""Pre-flight check for other work competing with a benchmark run.

Added 2026-10-09 after a teammate's Unity smoke test (`timeout 8 boombrawl.x86_64 -batchmode`)
ignored SIGTERM and sat at 100% of a core for 70+ minutes on this rig: anything like that skews
CPU-bound results (CPU-MoE paging, `--fit` expert offload, the dotnet/node test steps), and a
leftover llama-server or vLLM holding VRAM skews or breaks GPU runs.

`run.sh` calls this before launching bench.py. It prints warnings and exits 0, or exits 1 when
BENCH_ABORT_ON_BUSY=1 and something was found.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

CPU_THRESHOLD_PCT = 50.0      # of one core, measured over SAMPLE_WINDOW_S
VRAM_THRESHOLD_MIB = 3000     # Windows/WSL keeps ~1.5 GB on the display GPU at idle
SAMPLE_WINDOW_S = 2.0


def evaluate(
    procs: list[tuple[int, float, str]],
    gpus: list[tuple[int, int]],
    ignore_pids: set[int],
    cpu_threshold: float = CPU_THRESHOLD_PCT,
    vram_threshold: int = VRAM_THRESHOLD_MIB,
) -> list[str]:
    """procs: (pid, %cpu, command); gpus: (index, MiB used). Returns warning lines."""
    warnings = []
    for pid, cpu, cmd in sorted(procs, key=lambda p: -p[1]):
        if pid in ignore_pids or cpu < cpu_threshold:
            continue
        warnings.append(f"CPU: pid {pid} at {cpu:.0f}% of a core: {cmd[:120]}")
    for index, used in gpus:
        if used >= vram_threshold:
            warnings.append(f"GPU{index}: {used} MiB VRAM already in use before the run")
    return warnings


def _cpu_ticks() -> dict[int, int]:
    ticks = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            ticks[int(entry)] = int(fields[11]) + int(fields[12])  # utime + stime
        except (OSError, IndexError, ValueError):
            continue
    return ticks


def _cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def _processes(window_s: float = SAMPLE_WINDOW_S) -> list[tuple[int, float, str]]:
    """Current %CPU (of one core) per process over a short window. ps %CPU is a lifetime
    average, which misses a process that just started a burst and over-counts old work."""
    hz = os.sysconf("SC_CLK_TCK")
    before = _cpu_ticks()
    time.sleep(window_s)
    after = _cpu_ticks()
    rows = []
    for pid, t1 in after.items():
        t0 = before.get(pid)
        if t0 is None:
            continue
        pct = (t1 - t0) / hz / window_s * 100.0
        if pct > 0:
            rows.append((pid, pct, _cmdline(pid)))
    return rows


def _gpus() -> list[tuple[int, int]]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    gpus = []
    for line in out.splitlines():
        idx, used = (x.strip() for x in line.split(","))
        gpus.append((int(idx), int(used)))
    return gpus


def _ancestors(pid: int) -> set[int]:
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            with open(f"/proc/{pid}/stat") as f:
                pid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return seen


def main() -> int:
    warnings = evaluate(_processes(), _gpus(), _ancestors(os.getpid()))
    if not warnings:
        return 0
    print("[load-check] other work is running and may skew or break this benchmark:", file=sys.stderr)
    for w in warnings:
        print(f"  {w}", file=sys.stderr)
    if os.environ.get("BENCH_ABORT_ON_BUSY") == "1":
        print("[load-check] aborting (BENCH_ABORT_ON_BUSY=1).", file=sys.stderr)
        return 1
    print("[load-check] continuing; set BENCH_ABORT_ON_BUSY=1 to abort instead.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
