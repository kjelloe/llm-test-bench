from pathlib import Path

ANSWER_FILE = Path(__file__).parent.parent / "answer.txt"
EXPECTED = "RC-8803"


def test_sentinel_value():
    text = ANSWER_FILE.read_text(encoding="utf-8").strip()
    assert text == EXPECTED, f"Expected {EXPECTED!r}, got {text!r}"
