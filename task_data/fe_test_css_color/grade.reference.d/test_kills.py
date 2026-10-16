"""Grader for fe_test_css_color: the model's tests must pass on the real CssColor.cs, and each hidden faulty version
in mutants/ counts as caught when at least one of those tests fails against it. Partial credit = share caught."""
import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "Fastengine" / "CssColor.cs"
TESTS = ROOT / "tests" / "FastengineTests" / "CssColorTests.cs"
MUTANTS = sorted((pathlib.Path(__file__).parent / "mutants").glob("*.cs"))
FORBIDDEN = re.compile(r"\bFile\b|\bDirectory\b|CssColor\.cs|Reflection|GetType\(\)\.|typeof\(CssColor\)\.|Assembly|Process\b|Environment\.")


def _code(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


def _run():
    r = subprocess.run(["dotnet", "test", "--verbosity", "quiet"], cwd=ROOT, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=300)
    out = r.stdout + r.stderr
    m = re.search(r"Failed:\s+(\d+), Passed:\s+(\d+)", out)
    return r.returncode, (int(m.group(1)), int(m.group(2))) if m else None, out


@pytest.fixture(scope="session")
def real():
    return _run()


def test_tests_only_call_the_public_api():
    hit = FORBIDDEN.search(_code(TESTS.read_text(encoding="utf-8")))
    assert hit is None, f"tests must exercise CssColor through its API, not read files or reflect: {hit.group(0)!r}"


def test_your_tests_pass_on_the_real_code(real):
    rc, counts, out = real
    assert rc == 0 and counts and counts[1] > 0, out[-4000:]


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda p: p.stem)
def test_catches_fault(real, mutant):
    rc, counts, _ = real
    assert rc == 0 and counts, "your tests must pass on the real CssColor.cs before faults count"
    assert FORBIDDEN.search(_code(TESTS.read_text(encoding="utf-8"))) is None, "tests read files or reflect"
    original = SRC.read_bytes()
    try:
        shutil.copyfile(mutant, SRC)
        _, found, out = _run()
    finally:
        SRC.write_bytes(original)
    assert found is not None, "the tests did not build against a faulty CssColor.cs:\n" + out[-2000:]
    assert found[0] > 0, "no test failed with this fault"
