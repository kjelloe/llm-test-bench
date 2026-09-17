"""Regression test for powerlimit.sh's WSL2 PowerShell one-liner generation.

Not a Python unit test in the usual sense (there is no Python module behind
powerlimit.sh), but this printf template generates a command line that gets
re-parsed by two more shells downstream (the invoking shell, then PowerShell),
and it has already broken once in exactly that way -- worth a real regression
test rather than trusting eyeballing it again next time it's touched.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _is_wsl() -> bool:
    try:
        version = Path("/proc/version").read_text().lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


# Only WSL2 takes the print-only path exercised here; elsewhere powerlimit.sh
# falls through to `sudo nvidia-smi -pl ...`, which would actually try to
# change real GPU power limits -- never safe to invoke unconditionally in a test.
@pytest.mark.skipif(not _is_wsl(), reason="powerlimit.sh's print-only path is WSL2-specific")
def test_per_gpu_powershell_command_has_no_embedded_quote_bug():
    """A prior version embedded a raw double quote inside a single-quoted
    -ArgumentList element (`'-Command "..."'`). Any outer shell's own quote
    parser closes its string at that first unescaped `"`, splitting the
    command in two: the truncated head becomes a PowerShell parse error
    ("missing terminator '"), and the tail runs as literal, unelevated
    commands in the invoking shell -- which is why GPU power-limit calls
    failed with "Insufficient Permissions" instead of prompting for UAC.
    """
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "powerlimit.sh"), "--per-gpu"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "powershell.exe -Command" in out
    assert "'-Command \"" not in out  # the exact bug pattern
    assert "'-NoExit','-Command','" in out  # array-based fix: no embedded quotes
