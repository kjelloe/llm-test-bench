"""llamacpp/hangwatch.sh: deciding whether the run log shows a task still in progress (a hang candidate)."""
import re
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "llamacpp" / "hangwatch.sh"


def in_progress(log: Path) -> str:
    func = re.search(r"^task_in_progress\(\) \{.*?^\}", SCRIPT.read_text(), re.S | re.M).group(0)
    out = subprocess.run(["bash", "-c", f'LOG="$1"; {func}\ntask_in_progress', "_", str(log)],
                         capture_output=True, text=True, timeout=10)
    return out.stdout.strip()


def test_a_task_without_a_result_is_in_progress(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("[1/2] model='m'  task='a' ... PASS  3.1s  40.0 tok/s\n[2/2] model='m'  task='b' ... \n")
    assert in_progress(log) == "[2/2] model='m'  task='b'"


def test_a_result_pushed_to_a_later_line_by_hwmonitor_still_counts(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("[1/1] model='m'  task='a' ... WARN 01:02:03 GPU0 power 260W\nFAIL(TESTS_STILL_FAIL)  80s  42.0 tok/s\n")
    assert in_progress(log) == ""


def test_no_task_yet(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("Started: 2026-10-10\n")
    assert in_progress(log) == ""
