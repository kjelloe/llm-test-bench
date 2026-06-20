#!/usr/bin/env python3
"""
hwmonitor.py — Live hardware watchdog for llm-test-bench benchmark runs.

Polls GPU (nvidia-smi), CPU (/sys/class/thermal), and RAM (/proc/meminfo)
at a configurable interval. Prints WARN/CRIT lines on threshold transitions.
On CRIT: sends SIGINT to bench.py, then SIGTERM after --abort-timeout seconds
if the process has not exited.

Usage:
  ./hwmonitor/hwmonitor.py [--interval 2] [--log output/hwmonitor.log] [--pid PID]
                            [--warn-gpu-temp 85] [--crit-gpu-temp 95]
                            [--warn-junction 90]  [--crit-junction 100]
                            [--warn-cpu-temp 85]  [--crit-cpu-temp 95]
                            [--warn-power-pct 95] [--warn-ram-pct 90]
                            [--abort-timeout 3]
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ── ANSI ─────────────────────────────────────────────────────────────────────

_R = "\033[0m"
_Y = "\033[93m"
_RE = "\033[91m"
_G = "\033[92m"
_B = "\033[1m"

def _strip(s: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", s)

def _warn_fmt(msg: str) -> str:  return f"{_Y}{_B}WARN{_R}      {msg}"
def _crit_fmt(msg: str) -> str:  return f"{_RE}{_B}CRIT{_R}      {msg}"
def _ok_fmt(msg: str) -> str:    return f"{_G}{_B}OK  {_R}      {msg}"

# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class GpuSample:
    index: int
    name: str
    temp_c: float | None
    junction_c: float | None
    power_draw_w: float | None
    power_limit_w: float | None
    vram_used_mb: int | None
    vram_total_mb: int | None
    util_pct: int | None

@dataclass
class Sample:
    ts: datetime
    gpus: list[GpuSample]
    cpu_temp_c: float | None
    ram_used_gb: float
    ram_total_gb: float

@dataclass
class Thresholds:
    warn_gpu_temp: float = 85.0
    crit_gpu_temp: float = 95.0
    warn_junction:  float = 90.0
    crit_junction:  float = 100.0
    warn_cpu_temp:  float = 85.0
    crit_cpu_temp:  float = 95.0
    warn_power_pct: float = 95.0
    warn_ram_pct:   float = 90.0

# ── GPU collection ────────────────────────────────────────────────────────────

def probe_hotspot() -> bool:
    """Return True if this driver supports temperature.gpu.hotspot."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu.hotspot",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and "not a valid" not in (r.stderr + r.stdout).lower()
    except Exception:
        return False


def collect_gpu(hotspot: bool) -> list[GpuSample]:
    base = "index,name,temperature.gpu,power.draw,power.limit,memory.used,memory.total,utilization.gpu"
    hot  = "index,name,temperature.gpu,temperature.gpu.hotspot,power.draw,power.limit,memory.used,memory.total,utilization.gpu"
    fields = hot if hotspot else base
    try:
        r = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return []
        gpus: list[GpuSample] = []
        for line in r.stdout.strip().splitlines():
            p = [x.strip() for x in line.split(",")]

            def _f(s: str) -> float | None:
                try: return float(s)
                except (ValueError, TypeError): return None

            def _i(s: str) -> int | None:
                try: return int(float(s))
                except (ValueError, TypeError): return None

            if hotspot:
                if len(p) < 9: continue
                gpus.append(GpuSample(
                    index=_i(p[0]) or 0, name=p[1],
                    temp_c=_f(p[2]), junction_c=_f(p[3]),
                    power_draw_w=_f(p[4]), power_limit_w=_f(p[5]),
                    vram_used_mb=_i(p[6]), vram_total_mb=_i(p[7]),
                    util_pct=_i(p[8]),
                ))
            else:
                if len(p) < 8: continue
                gpus.append(GpuSample(
                    index=_i(p[0]) or 0, name=p[1],
                    temp_c=_f(p[2]), junction_c=None,
                    power_draw_w=_f(p[3]), power_limit_w=_f(p[4]),
                    vram_used_mb=_i(p[5]), vram_total_mb=_i(p[6]),
                    util_pct=_i(p[7]),
                ))
        return gpus
    except Exception:
        return []


# ── CPU temp ──────────────────────────────────────────────────────────────────

def collect_cpu_temp() -> float | None:
    """Highest temp from /sys/class/thermal. Returns None on WSL2 or error."""
    best: float | None = None
    try:
        base = Path("/sys/class/thermal")
        if not base.exists():
            return None
        for zone in base.iterdir():
            temp_file = zone / "temp"
            if not temp_file.exists():
                continue
            try:
                raw = int(temp_file.read_text().strip())
                temp = raw / 1000.0
                if 0 < temp < 120 and (best is None or temp > best):
                    best = temp
            except Exception:
                continue
    except Exception:
        pass
    return best


# ── RAM ───────────────────────────────────────────────────────────────────────

def collect_ram() -> tuple[float, float]:
    """Returns (used_gb, total_gb)."""
    try:
        total_kb = avail_kb = 0
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total_kb = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail_kb = int(line.split()[1])
        total_gb = round(total_kb / 1024 / 1024, 1)
        used_gb  = round((total_kb - avail_kb) / 1024 / 1024, 1)
        return used_gb, total_gb
    except Exception:
        return 0.0, 0.0


# ── Process management ────────────────────────────────────────────────────────

def find_bench_pid() -> int | None:
    try:
        r = subprocess.run(
            ["pgrep", "-f", "bench.py"],
            capture_output=True, text=True, timeout=3,
        )
        pids = [int(p) for p in r.stdout.strip().splitlines() if p.strip().isdigit()]
        pids = [p for p in pids if p != os.getpid()]
        return pids[0] if pids else None
    except Exception:
        return None


def abort_bench(pid: int, abort_timeout: float, emit) -> None:
    """SIGINT → wait abort_timeout → SIGTERM if still alive."""
    try:
        os.kill(pid, signal.SIGINT)
        emit(f"  → SIGINT → PID {pid}")
    except ProcessLookupError:
        emit(f"  → PID {pid} already gone")
        return
    except PermissionError:
        emit(f"  → no permission to signal PID {pid}")
        return

    deadline = time.monotonic() + abort_timeout
    while time.monotonic() < deadline:
        time.sleep(0.2)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            emit(f"  → PID {pid} exited after SIGINT")
            return

    try:
        os.kill(pid, signal.SIGTERM)
        emit(f"  → SIGTERM → PID {pid} (no exit within {abort_timeout:.0f}s)")
    except ProcessLookupError:
        emit(f"  → PID {pid} exited before SIGTERM")
    except PermissionError:
        emit(f"  → no permission to SIGTERM PID {pid}")


# ── Formatting ────────────────────────────────────────────────────────────────

def _short(name: str) -> str:
    m = re.search(r"(\d{4}(?:\s*Ti)?)", name, re.I)
    return m.group(1).replace(" ", "") if m else name[:8]


def format_line(s: Sample) -> str:
    ts = s.ts.strftime("%H:%M:%S")
    parts: list[str] = [ts + " "]

    for g in s.gpus:
        temp = f"{g.temp_c:.0f}°C"       if g.temp_c is not None       else "?°C"
        jct  = f" jct:{g.junction_c:.0f}°C" if g.junction_c is not None else ""
        pwr  = (f"{g.power_draw_w:.0f}W/{g.power_limit_w:.0f}W"
                if g.power_draw_w is not None and g.power_limit_w else "?W")
        vram = (f"{g.vram_used_mb/1024:.1f}/{g.vram_total_mb/1024:.1f}GB"
                if g.vram_used_mb is not None and g.vram_total_mb else "?GB")
        util = f"{g.util_pct}%" if g.util_pct is not None else "?%"
        parts.append(f"GPU{g.index}[{_short(g.name)}] {temp}{jct} {pwr} {vram} {util}")

    cpu = f"{s.cpu_temp_c:.0f}°C" if s.cpu_temp_c is not None else "N/A"
    parts.append(f"CPU {cpu}")
    parts.append(f"RAM {s.ram_used_gb}/{s.ram_total_gb}GB")

    return "  ".join(parts)


# ── Threshold state machine ───────────────────────────────────────────────────
# State per metric key: "OK" | "WARN" | "CRIT"
# Emit an alert only when the state changes, preventing repeat noise.

def _eval(
    key: str,
    value: float,
    warn: float,
    crit: float | None,
    label: str,
    prev: dict[str, str],
    out: list[tuple[str, str]],  # (level, msg) to emit
) -> str:
    if crit is not None and value >= crit:
        level = "CRIT"
        msg   = f"{label} {value:.0f} ≥ {crit:.0f}"
    elif value >= warn:
        level = "WARN"
        msg   = f"{label} {value:.0f} ≥ {warn:.0f}"
    else:
        level = "OK"
        msg   = f"{label} recovered ({value:.0f})"

    if level != prev.get(key, "OK"):
        out.append((level, msg))
    return level


def check_thresholds(
    s: Sample, t: Thresholds, prev: dict[str, str]
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    alerts: list[tuple[str, str]] = []
    new: dict[str, str] = {}

    for g in s.gpus:
        tag = f"GPU{g.index}[{_short(g.name)}]"

        if g.temp_c is not None:
            new[f"g{g.index}_temp"] = _eval(
                f"g{g.index}_temp", g.temp_c,
                t.warn_gpu_temp, t.crit_gpu_temp,
                f"{tag} core temp °C", prev, alerts,
            )

        if g.junction_c is not None:
            new[f"g{g.index}_jct"] = _eval(
                f"g{g.index}_jct", g.junction_c,
                t.warn_junction, t.crit_junction,
                f"{tag} junction temp °C", prev, alerts,
            )

        if g.power_draw_w is not None and g.power_limit_w:
            pct = g.power_draw_w / g.power_limit_w * 100
            new[f"g{g.index}_pwr"] = _eval(
                f"g{g.index}_pwr", pct,
                t.warn_power_pct, None,
                f"{tag} power {g.power_draw_w:.0f}W/{g.power_limit_w:.0f}W pct", prev, alerts,
            )

    if s.cpu_temp_c is not None:
        new["cpu_temp"] = _eval(
            "cpu_temp", s.cpu_temp_c,
            t.warn_cpu_temp, t.crit_cpu_temp,
            "CPU temp °C", prev, alerts,
        )

    if s.ram_total_gb > 0:
        ram_pct = s.ram_used_gb / s.ram_total_gb * 100
        new["ram"] = _eval(
            "ram", ram_pct,
            t.warn_ram_pct, None,
            f"RAM {s.ram_used_gb}/{s.ram_total_gb}GB pct", prev, alerts,
        )

    # Carry forward unchanged keys so they don't reset to OK
    for k, v in prev.items():
        if k not in new:
            new[k] = v

    return alerts, new


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hardware watchdog for benchmark runs.")
    p.add_argument("--interval",       type=float, default=2.0,  metavar="S",
                   help="Poll interval in seconds (default: 2)")
    p.add_argument("--log",            default="output/hwmonitor.log", metavar="FILE",
                   help="Log file path (default: output/hwmonitor.log)")
    p.add_argument("--pid",            type=int,   default=None, metavar="PID",
                   help="bench.py PID to abort on CRIT (auto-detected if omitted)")
    p.add_argument("--abort-timeout",  type=float, default=3.0,  metavar="S",
                   help="Seconds between SIGINT and SIGTERM (default: 3)")
    p.add_argument("--warn-gpu-temp",  type=float, default=85.0, metavar="C")
    p.add_argument("--crit-gpu-temp",  type=float, default=95.0, metavar="C")
    p.add_argument("--warn-junction",  type=float, default=90.0, metavar="C")
    p.add_argument("--crit-junction",  type=float, default=100.0, metavar="C")
    p.add_argument("--warn-cpu-temp",  type=float, default=85.0, metavar="C")
    p.add_argument("--crit-cpu-temp",  type=float, default=95.0, metavar="C")
    p.add_argument("--warn-power-pct", type=float, default=95.0, metavar="PCT")
    p.add_argument("--warn-ram-pct",   type=float, default=90.0, metavar="PCT")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    thresholds = Thresholds(
        warn_gpu_temp=args.warn_gpu_temp,
        crit_gpu_temp=args.crit_gpu_temp,
        warn_junction=args.warn_junction,
        crit_junction=args.crit_junction,
        warn_cpu_temp=args.warn_cpu_temp,
        crit_cpu_temp=args.crit_cpu_temp,
        warn_power_pct=args.warn_power_pct,
        warn_ram_pct=args.warn_ram_pct,
    )

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("a", encoding="utf-8")

    def emit(msg: str) -> None:
        print(msg, flush=True)
        print(_strip(msg), file=log_fh, flush=True)

    hotspot = probe_hotspot()
    bench_pid: int | None = args.pid
    aborted_pids: set[int] = set()
    states: dict[str, str] = {}

    emit(f"hwmonitor started  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit(f"  interval={args.interval}s  log={args.log}  "
         f"hotspot={'yes' if hotspot else 'no (driver too old — using core temp only)'}")
    emit(f"  thresholds: gpu≥{thresholds.warn_gpu_temp:.0f}°C/CRIT{thresholds.crit_gpu_temp:.0f}°C  "
         f"junction≥{thresholds.warn_junction:.0f}°C/CRIT{thresholds.crit_junction:.0f}°C  "
         f"cpu≥{thresholds.warn_cpu_temp:.0f}°C/CRIT{thresholds.crit_cpu_temp:.0f}°C  "
         f"power≥{thresholds.warn_power_pct:.0f}%  ram≥{thresholds.warn_ram_pct:.0f}%")

    if bench_pid:
        emit(f"  watching bench.py PID {bench_pid}")
    else:
        detected = find_bench_pid()
        if detected:
            bench_pid = detected
            emit(f"  auto-detected bench.py PID {bench_pid}")
        else:
            emit("  bench.py not running yet — will auto-detect on first CRIT")

    emit("")

    try:
        while True:
            ram_used, ram_total = collect_ram()
            s = Sample(
                ts=datetime.now(),
                gpus=collect_gpu(hotspot),
                cpu_temp_c=collect_cpu_temp(),
                ram_used_gb=ram_used,
                ram_total_gb=ram_total,
            )

            emit(format_line(s))

            alerts, states = check_thresholds(s, thresholds, states)

            for level, msg in alerts:
                ts = s.ts.strftime("%H:%M:%S")
                if level == "OK":
                    emit(_ok_fmt(f"{ts}  {msg}"))
                elif level == "WARN":
                    emit(_warn_fmt(f"{ts}  {msg}"))
                elif level == "CRIT":
                    # Re-detect bench_pid if not set
                    if bench_pid is None:
                        bench_pid = find_bench_pid()

                    pid_note = (
                        f" — aborting bench.py PID {bench_pid}"
                        if bench_pid and bench_pid not in aborted_pids
                        else " — no bench.py to abort" if not bench_pid
                        else f" — bench.py PID {bench_pid} already signalled"
                    )
                    emit(_crit_fmt(f"{ts}  {msg}{pid_note}"))

                    if bench_pid and bench_pid not in aborted_pids:
                        aborted_pids.add(bench_pid)
                        abort_bench(bench_pid, args.abort_timeout, emit)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        emit(f"\nhwmonitor stopped  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    finally:
        log_fh.close()


if __name__ == "__main__":
    main()
