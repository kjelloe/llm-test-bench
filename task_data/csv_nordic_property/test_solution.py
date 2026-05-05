"""Tests for solution.py — Norwegian property CSV task."""
import csv
import os
import subprocess
import sys

import pytest

_result: subprocess.CompletedProcess | None = None


def _run() -> None:
    global _result
    if _result is None:
        _result = subprocess.run(
            [sys.executable, "solution.py"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    if _result.returncode != 0:
        pytest.fail(f"solution.py exited {_result.returncode}:\n{_result.stderr}")


def _answers() -> list[str]:
    _run()
    return open("answers.txt", encoding="utf-8").read().splitlines()


# ── Q1–Q10 ────────────────────────────────────────────────────────────────────

def test_q1_total_regions():
    assert _answers()[0] == "5000"

def test_q2_regions_with_2023_data():
    assert _answers()[1] == "3900"

def test_q3_highest_2023_region():
    assert _answers()[2] == "0301 Oslo - Oslove"

def test_q4_national_2023_total():
    assert _answers()[3] == "2568222940"

def test_q5_peak_transaction_year():
    assert _answers()[4] == "2021"

def test_q6_synthetic_regions():
    assert _answers()[5] == "27"

def test_q7_billion_regions():
    assert _answers()[6] == "419"

def test_q8_growth_regions():
    assert _answers()[7] == "1287"

def test_q9_median():
    assert _answers()[8] == "149672"

def test_q10_top_growth_region():
    assert _answers()[9] == "0301 Oslo - Oslove"


# ── output.csv ────────────────────────────────────────────────────────────────

def test_output_exists():
    _run()
    assert os.path.exists("output.csv"), "output.csv was not created"


def test_output_row_count():
    _run()
    with open("output.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    assert len(rows) == 1950, f"expected 1950 rows, got {len(rows)}"


def test_output_columns():
    _run()
    with open("output.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        first = next(reader)
    cols = set(first.keys())
    expected = {
        "region",
        "1992 Omsetninger (antall)",
        "1992 Samlet kjøpesum (1 000 kr)",
        "1992 Gjennomsnittlig kjøpesum per omsetning (1 000 kr)",
        "2022 Omsetninger (antall)",
        "2022 Samlet kjøpesum (1 000 kr)",
        "2022 Gjennomsnittlig kjøpesum per omsetning (1 000 kr)",
    }
    missing = expected - cols
    assert not missing, f"output.csv is missing columns: {missing}"
    assert cols == expected, f"output.csv has unexpected extra columns: {cols - expected}"


def test_output_sorted_ascending():
    _run()
    with open("output.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    # Smallest 2023 value is in row 0; largest is in last row
    assert rows[0]["region"] == "1262 OSLO", f"expected first row '1262 OSLO', got {rows[0]['region']}"
    assert rows[-1]["region"] == "0301 Oslo - Oslove", f"expected last row '0301 Oslo - Oslove', got {rows[-1]['region']}"
