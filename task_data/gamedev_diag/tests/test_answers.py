"""Grades answers/<id>.txt against a salted hash of the correct letter, so the key does not
give the answers away. Each task runs only its own question (pytest -k <id>)."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "tests" / "answer_key.json").read_text())


def letter(text: str) -> str:
    stripped = text.strip()
    return stripped[:1].upper() if stripped[:1].upper() in "ABCDE" and stripped[:1] else ""


@pytest.mark.parametrize("qid", sorted(KEY))
def test_answer(qid):
    given = letter((ROOT / "answers" / f"{qid}.txt").read_text())
    assert given, f"answers/{qid}.txt must start with one of A-E"
    assert hashlib.sha256(f"gamedev_diag:{qid}:{given}".encode()).hexdigest() == KEY[qid], f"{qid}: {given} is not the best answer"
