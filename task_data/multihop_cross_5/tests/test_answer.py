from pathlib import Path

ANSWER_FILE = Path(__file__).parent.parent / "answer.txt"
EXPECTED = "oncall-emea-w-high@corp.example"


def test_oncall_contact():
    text = ANSWER_FILE.read_text(encoding="utf-8").strip().lower()
    assert text == EXPECTED, f"Expected {EXPECTED!r}, got {text!r}"
