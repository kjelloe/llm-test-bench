"""Capture a point-in-time hardware snapshot: GPU, CPU, RAM, platform, software versions."""
from __future__ import annotations

import platform
import re
import subprocess
from pathlib import Path


def get_hw_snapshot(
    llama_server_bin: str | None = None,
    models_dir: str | None = None,
) -> dict:
    """Return a dict with gpu, cpu, ram, platform, and optional software/storage info."""
    # Resolve model storage path: explicit dir (llama-server) or Ollama's store
    _storage_path = (
        models_dir
        or _ollama_models_dir()
    )
    snap: dict = {
        "gpu":            _gpu_info(),
        "cpu":            _cpu_info(),
        "ram_total_gb":   _ram_gb(),
        "platform":       f"{platform.system()} {platform.release()}",
        "cuda_toolkit":   _cuda_toolkit(),
        "ollama_version": _ollama_version(),
        "models_storage": _storage_type(_storage_path) if _storage_path else {},
    }
    if llama_server_bin:
        snap["llama_server_version"] = _llama_server_version(llama_server_bin)
    return snap


def hw_summary(hw: dict) -> str:
    """One-line summary for table headers."""
    parts = []
    for g in hw.get("gpu") or []:
        vram = round(g.get("vram_total_mb", 0) / 1024)
        pl = g.get("power_limit_w")
        pl_max = g.get("power_limit_max_w")
        label = f"{g['name']} {vram}GB"
        if pl is not None and pl_max is not None and pl < pl_max:
            label += f" [{pl:.0f}/{pl_max:.0f}W]"
        parts.append(label)
    cpu = hw.get("cpu") or ""
    if cpu and cpu != "unknown":
        parts.append(cpu)
    ram = hw.get("ram_total_gb") or 0
    if ram:
        parts.append(f"{ram} GB RAM")
    lsv = hw.get("llama_server_version")
    if lsv:
        parts.append(f"llama-server {lsv}")
    return "  |  ".join(parts) if parts else "unknown hardware"


# ── GPU ───────────────────────────────────────────────────────────────────────

def _gpu_info() -> list[dict]:
    """GPU list via nvidia-smi, including thermal, power, and compute capability."""
    # Try with compute_cap first; older drivers may not support that field.
    for fields, has_cap in (
        (
            "name,memory.total,memory.free,driver_version,"
            "temperature.gpu,power.draw,power.limit,power.max_limit,"
            "clocks.gr,clocks.max.gr,compute_cap",
            True,
        ),
        (
            "name,memory.total,memory.free,driver_version,"
            "temperature.gpu,power.draw,power.limit,power.max_limit,"
            "clocks.gr,clocks.max.gr",
            False,
        ),
    ):
        try:
            r = subprocess.run(
                ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                continue
            gpus = []
            for line in r.stdout.strip().splitlines():
                p = [x.strip() for x in line.split(",")]
                if len(p) < 10:
                    continue

                def _int(s: str) -> int | None:
                    try:
                        return int(float(s))
                    except (ValueError, TypeError):
                        return None

                def _float(s: str) -> float | None:
                    try:
                        return round(float(s), 1)
                    except (ValueError, TypeError):
                        return None

                entry = {
                    "name":              p[0],
                    "vram_total_mb":     _int(p[1]),
                    "vram_free_mb":      _int(p[2]),
                    "driver":            p[3],
                    "temp_c":            _int(p[4]),
                    "power_draw_w":      _float(p[5]),
                    "power_limit_w":     _float(p[6]),
                    "power_limit_max_w": _float(p[7]),
                    "clock_mhz":         _int(p[8]),
                    "clock_max_mhz":     _int(p[9]),
                }
                if has_cap and len(p) >= 11:
                    entry["compute_cap"] = _float(p[10])
                gpus.append(entry)
            return gpus
        except Exception:
            continue
    return []


# ── CPU ───────────────────────────────────────────────────────────────────────

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


# ── RAM ───────────────────────────────────────────────────────────────────────

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
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024 / 1024, 1)
    except Exception:
        pass
    return 0.0


# ── CUDA toolkit ──────────────────────────────────────────────────────────────

def _cuda_toolkit() -> str:
    """CUDA toolkit version from nvcc or version files; '' if not found."""
    # Prefer versioned dirs over /usr/bin/nvcc (Ubuntu apt installs old toolkit there)
    nvcc_candidates = []
    for d in sorted(Path("/usr/local").glob("cuda-*"), reverse=True):
        nvcc = d / "bin" / "nvcc"
        if nvcc.is_file():
            nvcc_candidates.append(str(nvcc))
    try:
        import shutil
        path_nvcc = shutil.which("nvcc")
        if path_nvcc and path_nvcc not in nvcc_candidates:
            nvcc_candidates.append(path_nvcc)
    except Exception:
        pass

    for nvcc in nvcc_candidates:
        try:
            out = subprocess.run(
                [nvcc, "--version"], capture_output=True, text=True, timeout=5,
            ).stdout
            m = re.search(r"release\s+([0-9]+\.[0-9]+)", out)
            if m:
                return m.group(1)
        except Exception:
            continue

    # Fall back to version files
    for vf in ["/usr/local/cuda/version.json", "/usr/local/cuda/version.txt"]:
        try:
            text = Path(vf).read_text()
            m = re.search(r"[0-9]+\.[0-9]+\.[0-9]+", text)
            if m:
                return m.group(0)
        except Exception:
            pass
    return ""


# ── Software versions ─────────────────────────────────────────────────────────

def _llama_server_version(bin_path: str) -> str:
    """Version string from llama-server --version; '' on failure."""
    try:
        r = subprocess.run(
            [bin_path, "--version"], capture_output=True, text=True, timeout=10,
        )
        out = (r.stdout + r.stderr).strip()
        # Typical output: "version: 1234 (abc1234)" or "llama-server version 1234 (abc1234)"
        m = re.search(r"version[:\s]+([0-9a-f.]+(?:\s*\([0-9a-f]+\))?)", out, re.I)
        return m.group(1).strip() if m else out.splitlines()[0][:80] if out else ""
    except Exception:
        return ""


def _ollama_version() -> str:
    """Ollama version string; '' if ollama not installed."""
    try:
        r = subprocess.run(
            ["ollama", "--version"], capture_output=True, text=True, timeout=5,
        )
        out = (r.stdout + r.stderr).strip()
        # "ollama version is 0.x.y" or "0.x.y"
        m = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", out)
        return m.group(1) if m else out[:40]
    except Exception:
        return ""


# ── Storage type ─────────────────────────────────────────────────────────────

def _ollama_models_dir() -> str:
    """Return Ollama's model directory: $OLLAMA_MODELS or ~/.ollama/models."""
    import os
    d = os.environ.get("OLLAMA_MODELS") or str(Path.home() / ".ollama" / "models")
    return d if Path(d).exists() else ""

def _storage_type(path_str: str) -> dict:
    """Best-effort storage transport for a given path.

    Returns e.g. {"device": "nvme0n1", "transport": "nvme"}
    or {"device": "/mnt/c", "transport": "windows-drive"} on WSL2.
    """
    result: dict = {"device": "", "transport": ""}
    try:
        path = Path(path_str).resolve()
        # Use df to find the filesystem source for this path
        r = subprocess.run(
            ["df", "--output=source", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return result
        lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            return result
        source = lines[-1]
        result["device"] = source

        if not source.startswith("/dev/"):
            # Network, virtual, or WSL2 Windows mount
            if re.match(r"[A-Za-z]:\\", source) or source in ("C:", "D:", "E:"):
                result["transport"] = "windows-drive"
            elif "/" in source and not source.startswith("/dev"):
                # Could be a network mount like //server/share or drvfs
                result["transport"] = "network-or-virtual"
            else:
                result["transport"] = source  # tmpfs, overlay, drvfs, etc.
            return result

        # Strip partition suffix: nvme0n1p2 -> nvme0n1 ; sda1 -> sda
        dev_name = Path(source).name
        dev_name = re.sub(r"p\d+$", "", dev_name)   # nvme partitions
        dev_name = re.sub(r"\d+$",  "", dev_name)    # sda/sdb partitions
        result["device"] = dev_name

        if dev_name.startswith("nvme"):
            result["transport"] = "nvme"
            return result

        rota_path = Path(f"/sys/block/{dev_name}/queue/rotational")
        if rota_path.exists():
            rota = rota_path.read_text().strip()
            result["transport"] = "hdd" if rota == "1" else "ssd"

    except Exception:
        pass
    return result
