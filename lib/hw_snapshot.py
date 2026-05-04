"""Capture a point-in-time hardware snapshot: GPU, CPU, RAM, platform."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def get_hw_snapshot() -> dict:
    """Return a dict with gpu, cpu, ram_total_gb, platform."""
    return {
        "gpu": _gpu_info(),
        "cpu": _cpu_info(),
        "ram_total_gb": _ram_gb(),
        "platform": f"{platform.system()} {platform.release()}",
    }


def hw_summary(hw: dict) -> str:
    """One-line summary, e.g. 'RTX 4090 24GB  |  Ryzen 9 7950X (32c)  |  128.0 GB RAM'"""
    parts = []
    for g in hw.get("gpu") or []:
        vram = round(g.get("vram_total_mb", 0) / 1024)
        parts.append(f"{g['name']} {vram}GB")
    cpu = hw.get("cpu") or ""
    if cpu and cpu != "unknown":
        parts.append(cpu)
    ram = hw.get("ram_total_gb") or 0
    if ram:
        parts.append(f"{ram} GB RAM")
    return "  |  ".join(parts) if parts else "unknown hardware"


def _gpu_info() -> list[dict]:
    """GPU list via nvidia-smi. Returns [] if unavailable."""
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return []
        gpus = []
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                gpus.append({
                    "name": parts[0],
                    "vram_total_mb": int(parts[1]),
                    "driver": parts[2],
                })
        return gpus
    except Exception:
        return []


def _cpu_info() -> str:
    """CPU model string with logical core count."""
    if platform.system() == "Darwin":
        try:
            brand = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
            cores = subprocess.run(
                ["sysctl", "-n", "hw.logicalcpu"],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
            return f"{brand} ({cores} logical cores)"
        except Exception:
            return "unknown"
    # Linux / WSL2
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        name = "unknown"
        for line in text.splitlines():
            if line.startswith("model name"):
                name = line.split(":", 1)[1].strip()
                break
        cores = text.count("processor\t:")
        return f"{name} ({cores} logical cores)"
    except Exception:
        return "unknown"


def _ram_gb() -> float:
    """Total system RAM in GB."""
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
            return round(int(out) / 1024 ** 3, 1)
        except Exception:
            return 0.0
    # Linux / WSL2
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                return round(kb / 1024 / 1024, 1)
    except Exception:
        pass
    return 0.0
