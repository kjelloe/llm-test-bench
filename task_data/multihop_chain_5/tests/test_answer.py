from pathlib import Path

ANSWER_FILE = Path(__file__).parent.parent / "answer.txt"
EXPECTED = "90"


def test_retention_days():
    text = ANSWER_FILE.read_text(encoding="utf-8").strip()
    assert text == EXPECTED, f"Expected {EXPECTED!r}, got {text!r}"
