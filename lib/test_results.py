"""Partial credit: per-test outcomes parsed from test-runner output, weighted into a score.

A task's binary pass/fail stays the headline result; this adds how close a failing
solution came. Supported runners: xunit via `dotnet test --verbosity normal`, Node's
`node --test` spec reporter, and `pytest -v`.
"""
import re

_XUNIT = re.compile(r"^\s+(Passed|Failed) (\S.*?) \[[^\]]*\]\s*$", re.M)
_NODE = re.compile(r"^\s*([✔✖]) (.+?) \(\d[\d.]*m?s\)\s*$", re.M)
_PYTEST = re.compile(r"^(\S+::\S+) (PASSED|FAILED|ERROR)\b", re.M)

_XUNIT_SUMMARY = re.compile(r"Failed:\s+(\d+), Passed:\s+(\d+), Skipped:\s+\d+, Total:\s+(\d+)")
_XUNIT_NORMAL_SUMMARY = re.compile(r"Total tests: (\d+)\s+Passed: (\d+)")  # dotnet test --verbosity normal
_NODE_PASS = re.compile(r"^ℹ pass (\d+)$", re.M)
_NODE_FAIL = re.compile(r"^ℹ fail (\d+)$", re.M)
_PYTEST_SUMMARY = re.compile(r"=+ (.*\d+ (?:passed|failed).*?) in [\d.]+s")

# node --test prints a top-level "✖ <file>" when the test file itself cannot load.
_NODE_FILE_LEVEL = re.compile(r"^tests?$|\.test\.[cm]?js$")


def parse_outcomes(output: str) -> dict[str, bool]:
    """Test name -> passed, for every individually reported test."""
    outcomes: dict[str, bool] = {}
    for status, name in _XUNIT.findall(output):
        outcomes[name] = status == "Passed"
    for mark, name in _NODE.findall(output):
        if _NODE_FILE_LEVEL.search(name) or name == "failing tests:":
            continue
        # The spec reporter repeats failures in a trailing summary; a test never flips back to pass.
        outcomes[name] = outcomes.get(name, True) and mark == "✔"
    for name, status in _PYTEST.findall(output):
        outcomes[name] = status == "PASSED"
    return outcomes


def parse_counts(output: str) -> tuple[int, int] | None:
    """(passed, total) from the runner's summary line, when per-test lines are unavailable."""
    m = _XUNIT_SUMMARY.search(output)
    if m:
        return int(m.group(2)), int(m.group(3))
    m = _XUNIT_NORMAL_SUMMARY.search(output)
    if m:
        return int(m.group(2)), int(m.group(1))
    p, f = _NODE_PASS.search(output), _NODE_FAIL.search(output)
    if p and f:
        return int(p.group(1)), int(p.group(1)) + int(f.group(1))
    m = _PYTEST_SUMMARY.search(output)
    if m:
        counts = dict((k, int(v)) for v, k in re.findall(r"(\d+) (passed|failed|error)", m.group(1)))
        passed = counts.get("passed", 0)
        return passed, passed + counts.get("failed", 0) + counts.get("error", 0)
    return None


def weight_of(name: str, weights: dict[str, float] | None) -> float:
    """First weights key that is a substring of the test name wins; default 1."""
    for key, w in (weights or {}).items():
        if key in name:
            return w
    return 1.0


def score_output(output: str, weights: dict[str, float] | None = None) -> dict | None:
    """{passed, total, score, weighted} for one test run, or None if nothing was reported
    (for example a compile error before any test ran)."""
    outcomes = parse_outcomes(output)
    if outcomes:
        total_w = sum(weight_of(n, weights) for n in outcomes)
        passed_w = sum(weight_of(n, weights) for n, ok in outcomes.items() if ok)
        return {
            "passed": sum(outcomes.values()),
            "total": len(outcomes),
            "score": round(passed_w / total_w, 4) if total_w else 0.0,
            "weighted": True,
        }
    counts = parse_counts(output)
    if counts and counts[1]:
        passed, total = counts
        return {"passed": passed, "total": total, "score": round(passed / total, 4), "weighted": False}
    return None


def record_score(record: dict) -> float:
    """Partial credit for one result record: 1.0 for a pass, the stored test score for a
    failure, else a best-effort unweighted score from the stored (possibly truncated) test
    output of older records, else 0.0 (no code, compile error, timeout...)."""
    if record.get("tests_pass"):
        return 1.0
    stored = record.get("test_score")
    if stored:
        return stored["score"]
    if record.get("error_kind") == "TESTS_STILL_FAIL":
        counts = parse_counts(str(record.get("error_detail") or ""))
        if counts and counts[1]:
            return round(counts[0] / counts[1], 4)
    return 0.0
