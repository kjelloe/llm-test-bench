"""Pre-flight GPU power-limit safety check for multi-GPU runs.

nvidia-smi power limits (`nvidia-smi -pl`) reset to hardware default on every reboot and
are not applied automatically by this repo (see ./powerlimit.sh) — a user who forgets to
re-apply them after a restart could run 3+ uncapped GPUs at combined power the PSU wasn't
sized for. Added 2026-08-29 after an unexplained hard PC crash during sustained 3-GPU
compute-bound testing (power limits could not be confirmed in effect at the time) — see
hw-upgrade-july-2026.md for the full incident.

`run.sh` calls this module before launching bench.py in multi-GPU mode. It exits 1 (and
prints remediation guidance to stderr) if the check fails, 0 otherwise.
"""
from __future__ import annotations

import subprocess
import sys


def evaluate(
    limits: list[float],
    maxes: list[float],
    max_psu_watt: float,
    system_overhead_watt: float,
    min_gpus: int = 3,
) -> tuple[bool, str]:
    """Decide whether the current power-limit configuration is safe.

    Returns (is_safe, message). message is empty when is_safe is True.
    Fewer than `min_gpus` GPUs is always considered safe — this check targets the specific
    tight-PSU-headroom case of 3+ simultaneous GPUs, not smaller setups with ample margin.
    """
    if len(limits) < min_gpus:
        return True, ""
    total = sum(limits)
    budget = max_psu_watt - system_overhead_watt
    uncapped = sum(1 for l, m in zip(limits, maxes) if l >= m - 0.5)
    if not uncapped and total <= budget:
        return True, ""

    lines = [
        "=" * 70,
        f"ABORT: GPU power limits look unsafe for a {len(limits)}-GPU run.",
        f"  Current limits sum to {total:.0f}W; budget is {budget:.0f}W",
        f"  (MAX_PSU_WATT={max_psu_watt:.0f}W minus ~{system_overhead_watt:.0f}W system overhead).",
    ]
    if uncapped:
        lines += [
            f"  {uncapped} GPU(s) sit at their hardware power maximum — limits were",
            "  never set, or reset on the last reboot (nvidia-smi power limits are",
            "  NOT persistent across reboots — this is expected, not a bug).",
        ]
    lines += [
        "",
        "  Fix: run ./powerlimit.sh --per-gpu in an elevated Windows terminal.",
        "",
        "  If your PSU is not 1200W, set MAX_PSU_WATT to match, e.g.:",
        "    MAX_PSU_WATT=850 ./run.sh ...",
        "",
        "  To bypass (not recommended): SKIP_POWER_CHECK=1 ./run.sh ...",
        "=" * 70,
    ]
    return False, "\n".join(lines)


def _query_nvidia_smi() -> list[tuple[float, float]] | None:
    """Return [(power.limit, power.max_limit), ...] per GPU, or None if unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.limit,power.max_limit",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except Exception:
        return None
    rows = [line.split(",") for line in out.splitlines() if line.strip()]
    try:
        return [(float(r[0]), float(r[1])) for r in rows]
    except (ValueError, IndexError):
        return None


def main() -> None:
    max_psu_watt = float(sys.argv[1]) if len(sys.argv) > 1 else 1200.0
    system_overhead_watt = float(sys.argv[2]) if len(sys.argv) > 2 else 175.0

    rows = _query_nvidia_smi()
    if rows is None:
        sys.exit(0)  # nvidia-smi unavailable — nothing to check, let the run proceed

    limits = [r[0] for r in rows]
    maxes = [r[1] for r in rows]
    is_safe, message = evaluate(limits, maxes, max_psu_watt, system_overhead_watt)
    if not is_safe:
        print(message, file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
