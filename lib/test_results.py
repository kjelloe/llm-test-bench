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
    """{passed, total, score, weighted, failed} for one test run, or None if nothing was reported
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
            # The stored error_detail is truncated; keep the names so failures stay analysable.
            "failed": [n for n, ok in outcomes.items() if not ok][:50],
        }
    counts = parse_counts(output)
    if counts and counts[1]:
        passed, total = counts
        return {"passed": passed, "total": total, "score": round(passed / total, 4), "weighted": False, "failed": None}
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


# C# compiler errors (dotnet prints each twice: during the build and in its summary).
_CS_ERROR = re.compile(r"^(.*?)\berror (CS\d{4}): (.+?)(?: \[[^\]\n]*\])?\s*$", re.M)
_LANGUAGE_VERSION = re.compile(r"is not available in C# 9\.0")
_MISSING_FRAMEWORK = re.compile(r"does not exist in the namespace 'System[.']")


def unity_reason(code: str, message: str) -> str | None:
    """Why this error comes from Unity's constraints rather than a plain mistake, or None.
    Unity compiles C# 9 against .NET Standard 2.1, so newer language features and newer
    framework namespaces (System.Text.Json, ...) don't exist there."""
    if code == "CS8773" or _LANGUAGE_VERSION.search(message):
        return "language newer than C# 9"
    if code == "CS0518":
        return "type missing from .NET Standard 2.1"
    if code == "CS0234" and _MISSING_FRAMEWORK.search(message):
        return "namespace missing from .NET Standard 2.1"
    return None


def build_errors(output: str) -> dict | None:
    """{errors, codes, unity} for a run whose build failed, or None if it reported no C# errors.
    errors: distinct errors; codes: code -> distinct count; unity: the distinct Unity-constraint
    errors as "CSxxxx: message" (at most 10)."""
    seen: dict[str, tuple[str, str]] = {}
    for where, code, message in _CS_ERROR.findall(output):
        seen.setdefault(f"{where.strip()} {code} {message}", (code, message))
    if not seen:
        return None
    codes: dict[str, int] = {}
    unity: list[str] = []
    for code, message in seen.values():
        codes[code] = codes.get(code, 0) + 1
        if unity_reason(code, message) and f"{code}: {message}" not in unity:
            unity.append(f"{code}: {message}")
    return {"errors": len(seen), "codes": dict(sorted(codes.items())), "unity": unity[:10]}


def record_build(record: dict) -> dict | None:
    """Build errors for one result record: the stored field, else parsed from the stored (possibly
    truncated) error_detail of older records."""
    if record.get("tests_pass"):
        return None
    if "build_errors" in record:
        return record["build_errors"]
    if record.get("error_kind") == "TESTS_STILL_FAIL":
        return build_errors(str(record.get("error_detail") or ""))
    return None
