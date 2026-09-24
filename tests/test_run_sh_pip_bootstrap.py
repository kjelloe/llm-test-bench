"""Regression guard for run.sh's venv/pip setup.

Confirmed 2026-09-24 on a Debian-family box: `python3 -m venv .venv` can succeed while leaving
pip out entirely (Debian omits ensurepip's wheel unless python3-pip is installed at the OS
level), and a subsequent bare `pip install` then falls through PATH to the system's
externally-managed pip, which refuses with a confusing PEP 668 error instead of a clear
"pip missing" one. See feedback_debian_venv_pip.md and how-to-vllm.md.

Not a full behavioral test (that would mean spawning bench.py/hwmonitor for real) — just a
guard that the specific fallback and safe invocation pattern stay in place.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_RUN_SH = (REPO_ROOT / "run.sh").read_text()


def test_ensurepip_bootstrap_present():
    assert "ensurepip" in _RUN_SH, (
        "run.sh no longer bootstraps a missing venv pip via ensurepip — "
        "Debian/Ubuntu boxes without python3-pip will hit a confusing externally-managed-"
        "environment error again instead of a clear one (see 2026-09-24 finding)"
    )


def test_pip_invoked_via_venv_python_not_bare_pip():
    assert '"$VENV/bin/python3" -m pip install' in _RUN_SH, (
        "requirements.txt must be installed via the venv's own python3 -m pip, not a bare "
        "`pip install` — a bare call can silently resolve to the system's externally-managed "
        "pip instead of the venv's (see 2026-09-24 finding)"
    )
