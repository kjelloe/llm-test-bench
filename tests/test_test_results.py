"""lib/test_results.py: per-test outcome parsing and weighted partial credit."""
from lib.test_results import parse_counts, parse_outcomes, record_score, score_output, weight_of

XUNIT = """\
  Restored /tmp/x/src/GameClient/GameClient.csproj (in 47 ms).
[xUnit.net 00:00:00.10]     GameClientTests.T.Rotation [FAIL]
  Failed GameClientTests.T.Rotation [3 ms]
  Error Message:
   expected (0, 1) got (1, 0)
  Passed GameClientTests.T.Position [< 1 ms]
  Failed GameClientTests.T.Bad(json: "[1,2]", expected: BadShape) [2 ms]
  Passed GameClientTests.T.Bad(json: "{}", expected: BadShape) [< 1 ms]
Failed!  - Failed:     2, Passed:     2, Skipped:     0, Total:     4, Duration: 19 ms - GameClientTests.dll (net9.0)
"""

NODE = """\
✔ accepts a valid move (1.2ms)
✖ seq must strictly increase (0.4ms)
  AssertionError [ERR_ASSERTION]: Expected values to be strictly deep-equal:
✔ units() returns copies sorted by id (0.1ms)
ℹ tests 3
ℹ pass 2
ℹ fail 1
✖ failing tests:

test at tests/room.test.js:5:1
✖ seq must strictly increase (0.4ms)
"""

PYTEST = """\
tests/test_calc.py::test_ok PASSED                                       [ 50%]
tests/test_calc.py::test_zero FAILED                                     [100%]
=========================== short test summary info ============================
========================= 1 failed, 1 passed in 0.03s =========================
"""


def test_parses_xunit_including_theory_rows_with_brackets():
    out = parse_outcomes(XUNIT)
    assert out == {
        "GameClientTests.T.Rotation": False,
        "GameClientTests.T.Position": True,
        'GameClientTests.T.Bad(json: "[1,2]", expected: BadShape)': False,
        'GameClientTests.T.Bad(json: "{}", expected: BadShape)': True,
    }


def test_parses_node_and_ignores_the_repeated_failure_summary():
    out = parse_outcomes(NODE)
    assert out == {
        "accepts a valid move": True,
        "seq must strictly increase": False,
        "units() returns copies sorted by id": True,
    }


def test_parses_pytest_verbose():
    assert parse_outcomes(PYTEST) == {"tests/test_calc.py::test_ok": True, "tests/test_calc.py::test_zero": False}


def test_summary_counts_for_each_runner():
    assert parse_counts(XUNIT) == (2, 4)
    assert parse_counts(NODE) == (2, 3)
    assert parse_counts(PYTEST) == (1, 2)
    assert parse_counts("error CS0103: The name 'Unsafe' does not exist") is None
    normal = "Total tests: 13\n     Passed: 11\n     Failed: 2\n Total time: 0.33 Seconds"
    assert parse_counts(normal) == (11, 13)


def test_weighted_score():
    weights = {"Rotation": 3.0, "Bad(": 0.5}
    assert weight_of("GameClientTests.T.Rotation", weights) == 3.0
    assert weight_of("GameClientTests.T.Position", weights) == 1.0
    s = score_output(XUNIT, weights)
    # passed: Position (1) + Bad {} (0.5) = 1.5 of 3 + 1 + 0.5 + 0.5 = 5
    assert s["failed"] == ["GameClientTests.T.Rotation", 'GameClientTests.T.Bad(json: "[1,2]", expected: BadShape)']
    assert {k: s[k] for k in ("passed", "total", "score", "weighted")} == {"passed": 2, "total": 4, "score": 0.3, "weighted": True}
    assert score_output(XUNIT)["score"] == 0.5


def test_counts_fallback_when_per_test_lines_were_truncated_away():
    truncated = "…(truncated)…\nFailed!  - Failed:     3, Passed:     9, Skipped:     0, Total:    12, Duration: 5 ms"
    assert score_output(truncated) == {"passed": 9, "total": 12, "score": 0.75, "weighted": False, "failed": None}


def test_compile_error_scores_nothing():
    assert score_output("Build FAILED.\nerror CS8773: Feature 'unsigned right shift' is not available in C# 9.0.") is None


def test_record_score():
    assert record_score({"tests_pass": True}) == 1.0
    assert record_score({"tests_pass": False, "test_score": {"score": 0.4}}) == 0.4
    old = {"tests_pass": False, "error_kind": "TESTS_STILL_FAIL",
           "error_detail": "…\nℹ pass 12\nℹ fail 4\n"}
    assert record_score(old) == 0.75
    assert record_score({"tests_pass": False, "error_kind": "NO_BLOCKS", "error_detail": "ℹ pass 3\nℹ fail 1"}) == 0.0
    assert record_score({"tests_pass": False, "error_kind": "TESTS_STILL_FAIL", "error_detail": "error CS0103"}) == 0.0


DOTNET_BUILD_FAIL = """
  Restored /tmp/x/src/GameClient/GameClient.csproj (in 51 ms).
/tmp/x/src/GameClient/QrCode.cs(40,23): error CS8773: Feature 'unsigned right shift' is not available in C# 9.0. Please use language version 11.0 or greater. [/tmp/x/src/GameClient/GameClient.csproj]
/tmp/x/src/GameClient/QrCode.cs(51,9): error CS0136: A local or parameter named 'wanted' cannot be declared in this scope because that name is used in an enclosing local scope to define a local or parameter [/tmp/x/src/GameClient/GameClient.csproj]
/tmp/x/src/GameClient/Seat.cs(3,18): error CS0234: The type or namespace name 'Json' does not exist in the namespace 'System.Text' (are you missing an assembly reference?) [/tmp/x/src/GameClient/GameClient.csproj]
Build FAILED.
/tmp/x/src/GameClient/QrCode.cs(40,23): error CS8773: Feature 'unsigned right shift' is not available in C# 9.0. Please use language version 11.0 or greater. [/tmp/x/src/GameClient/GameClient.csproj]
/tmp/x/src/GameClient/QrCode.cs(51,9): error CS0136: A local or parameter named 'wanted' cannot be declared in this scope because that name is used in an enclosing local scope to define a local or parameter [/tmp/x/src/GameClient/GameClient.csproj]
/tmp/x/src/GameClient/Seat.cs(3,18): error CS0234: The type or namespace name 'Json' does not exist in the namespace 'System.Text' (are you missing an assembly reference?) [/tmp/x/src/GameClient/GameClient.csproj]
    3 Error(s)
"""


def test_build_errors_counts_distinct_errors_and_flags_unity_constraints():
    from lib.test_results import build_errors

    b = build_errors(DOTNET_BUILD_FAIL)
    assert b["errors"] == 3  # each is printed twice by dotnet
    assert b["codes"] == {"CS0136": 1, "CS0234": 1, "CS8773": 1}
    assert [u.split(":")[0] for u in b["unity"]] == ["CS8773", "CS0234"]
    assert build_errors("  Passed GameClientTests.X [1 ms]\nTotal tests: 1\n") is None


def test_record_build_falls_back_to_the_stored_output():
    from lib.test_results import record_build

    assert record_build({"tests_pass": True, "error_detail": DOTNET_BUILD_FAIL}) is None
    assert record_build({"tests_pass": False, "error_kind": "TESTS_STILL_FAIL", "error_detail": DOTNET_BUILD_FAIL})["errors"] == 3
    assert record_build({"tests_pass": False, "build_errors": None, "error_detail": DOTNET_BUILD_FAIL}) is None
