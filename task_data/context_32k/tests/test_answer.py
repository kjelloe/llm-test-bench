from pathlib import Path

ANSWER_FILE = Path(__file__).parent.parent / "answer.txt"
EXPECTED = "RC-2291"


def test_resolution_code():
    text = ANSWER_FILE.read_text(encoding="utf-8").strip()
    assert text == EXPECTED, f"Expected {EXPECTED!r}, got {text!r}"
