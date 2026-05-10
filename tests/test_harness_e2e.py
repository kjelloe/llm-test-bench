"""End-to-end harness self-test.

Uses a mock chat_fn (no Ollama or llama-server needed) to exercise the full
pipeline: prepare workdir → baseline → model call → parse → apply → tests.
Then feeds the collected records through the comparison table and skill-level
logic to verify reporting is consistent.
"""

import dataclasses
import io
import shutil
from contextlib import redirect_stdout

import pytest

from bench import run_one
from lib.llama_server_client import _parse_body
from lib.ollama_client import OllamaMetrics, OllamaResponse
from lib.reporting import _INFRA_ERROR_KINDS, _skill_level, print_comparison_table
from lib.tasks import PYTHON_SAFE_DIV

# Use python3 explicitly so the test works on systems where 'python' is not on PATH
TASK = dataclasses.replace(
    PYTHON_SAFE_DIV,
    test_cmd=["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
) if not shutil.which("python") else PYTHON_SAFE_DIV

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CORRECT_CALC = """\
def safe_div(a: float, b: float) -> float:
    \"\"\"Divide a by b. Must raise ValueError (not ZeroDivisionError) when b is 0.\"\"\"
    if b == 0:
        raise ValueError("division by zero")
    return a / b
"""

BROKEN_CALC = """\
def safe_div(a: float, b: float) -> float:
    return a / b
"""


def _metrics(prompt_tokens: int = 500, gen_tokens: int = 60) -> OllamaMetrics:
    eval_ns = gen_tokens * 50_000_000  # ~20 tok/s
    return OllamaMetrics(
        prompt_eval_count=prompt_tokens,
        eval_count=gen_tokens,
        prompt_eval_duration=prompt_tokens * 10_000_000,
        eval_duration=eval_ns,
        total_duration=prompt_tokens * 10_000_000 + eval_ns,
    )


def _mock_chat(response_text: str):
    """Return a chat_fn that always replies with response_text.

    prompt_eval_count is derived from the actual messages length so the
    ctx_truncated heuristic (prompt_eval_count < len(prompt) // 5) stays false.
    """
    def chat_fn(**kwargs):
        msg_len = sum(len(m.get("content", "")) for m in kwargs.get("messages", []))
        prompt_tokens = max(500, msg_len // 4)
        return OllamaResponse(
            content=response_text,
            thinking="",
            metrics=_metrics(prompt_tokens=prompt_tokens),
        )
    return chat_fn


def _file_block(content: str) -> str:
    return f"BEGIN_FILE calc.py\n{content}END_FILE\n"


# ---------------------------------------------------------------------------
# run_one pipeline tests
# ---------------------------------------------------------------------------

def test_run_one_pass():
    """Correct fix → tests_pass=True, no error_kind."""
    rec = run_one(
        model="mock-model",
        task=TASK,
        client_url="http://unused",
        num_ctx=4096,
        temperature=0.0,
        seed=1,
        num_predict=400,
        model_timeout=60,
        chat_fn=_mock_chat(_file_block(CORRECT_CALC)),
    )
    assert rec["tests_pass"] is True
    assert rec["error_kind"] is None
    assert rec["edit_parse_ok"] is True
    assert rec["edit_policy_ok"] is True
    assert rec["baseline_failed"] is True  # fixture must fail before fix


def test_run_one_no_blocks():
    """Model returns prose with no BEGIN_FILE blocks → NO_BLOCKS."""
    rec = run_one(
        model="mock-model",
        task=TASK,
        client_url="http://unused",
        num_ctx=4096,
        temperature=0.0,
        seed=1,
        num_predict=400,
        model_timeout=60,
        chat_fn=_mock_chat("Sorry, I cannot fix that."),
    )
    assert rec["tests_pass"] is False
    assert rec["error_kind"] == "NO_BLOCKS"
    assert rec["edit_parse_ok"] is False


def test_run_one_tests_still_fail():
    """Model returns syntactically valid block but wrong logic → TESTS_STILL_FAIL."""
    rec = run_one(
        model="mock-model",
        task=TASK,
        client_url="http://unused",
        num_ctx=4096,
        temperature=0.0,
        seed=1,
        num_predict=400,
        model_timeout=60,
        chat_fn=_mock_chat(_file_block(BROKEN_CALC)),
    )
    assert rec["tests_pass"] is False
    assert rec["error_kind"] == "TESTS_STILL_FAIL"
    assert rec["edit_parse_ok"] is True
    assert rec["edit_policy_ok"] is True


def test_run_one_edited_noneditable():
    """Model tries to edit a file outside the allow-list → EDITED_NONEDITABLE_FILE."""
    bad_output = (
        "BEGIN_FILE calc.py\n" + CORRECT_CALC + "END_FILE\n"
        "BEGIN_FILE tests/test_calc.py\n# hacked\nEND_FILE\n"
    )
    rec = run_one(
        model="mock-model",
        task=TASK,
        client_url="http://unused",
        num_ctx=4096,
        temperature=0.0,
        seed=1,
        num_predict=400,
        model_timeout=60,
        chat_fn=_mock_chat(bad_output),
    )
    assert rec["tests_pass"] is False
    assert rec["error_kind"] == "EDITED_NONEDITABLE_FILE"


# ---------------------------------------------------------------------------
# Comparison table + skill level tests
# ---------------------------------------------------------------------------

def _make_record(model: str, task: str, tests_pass: bool, error_kind: str | None = None,
                 difficulty: int = 1, tok_per_s: float = 20.0, wall_s: float = 3.0) -> dict:
    return {
        "model": model,
        "backend": "ollama",
        "task": task,
        "tests_pass": tests_pass,
        "error_kind": error_kind,
        "tok_per_s": tok_per_s,
        "wall_s": wall_s,
        "baseline_failed": True,
        "baseline_rc": 1,
        "edit_parse_ok": tests_pass,
        "edit_policy_ok": tests_pass,
        "response_truncated": False,
        "ctx_truncated": False,
        "response_snippet": None,
        "edited_files": [],
        "error_detail": None,
        "metrics": {},
        "kv_cache": None,
        "gpu_snapshots": None,
    }


def test_comparison_table_renders():
    """print_comparison_table must not raise and must emit PASS/FAIL cells."""
    results = [
        _make_record("good-model", "python_safe_div", tests_pass=True),
        _make_record("bad-model",  "python_safe_div", tests_pass=False, error_kind="NO_BLOCKS"),
    ]
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_comparison_table(results, task_difficulties={"python_safe_div": 1})
    out = buf.getvalue()
    assert "PASS" in out
    assert "FAIL" in out
    assert "good-model" in out
    assert "bad-model" in out


def test_skill_level_pass():
    results = [_make_record("m", "t1", True), _make_record("m", "t2", True)]
    idx = {(r["model"], r["task"]): r for r in results}
    assert _skill_level("m", ["t1", "t2"], idx, {"t1": 1, "t2": 2}) == "L2"


def test_skill_level_fail_at_l2():
    results = [_make_record("m", "t1", True), _make_record("m", "t2", False)]
    idx = {(r["model"], r["task"]): r for r in results}
    assert _skill_level("m", ["t1", "t2"], idx, {"t1": 1, "t2": 2}) == "L1"


def test_skill_level_infra_errors_not_penalised():
    """TOOL_ERROR, SKIPPED_CTX, SKIPPED_VRAM, CTX_TRUNCATED must not lower skill."""
    for kind in _INFRA_ERROR_KINDS:
        results = [
            _make_record("m", "t1", True),
            _make_record("m", "t2", False, error_kind=kind),
        ]
        idx = {(r["model"], r["task"]): r for r in results}
        skill = _skill_level("m", ["t1", "t2"], idx, {"t1": 1, "t2": 2})
        assert skill == "L2", f"Expected L2 for {kind!r} but got {skill!r}"


def test_skill_level_genuine_failure_penalised():
    """TESTS_STILL_FAIL must lower skill even at L1."""
    results = [
        _make_record("m", "t1", False, error_kind="TESTS_STILL_FAIL"),
    ]
    idx = {(r["model"], r["task"]): r for r in results}
    assert _skill_level("m", ["t1"], idx, {"t1": 1}) == "<L1"


# ---------------------------------------------------------------------------
# Fix 1: reasoning_content fallback in llama_server_client._parse_body
# ---------------------------------------------------------------------------

_ELAPSED = 1_000_000_000  # 1 s in nanoseconds (arbitrary for these tests)


def test_parse_body_reasoning_fallback():
    """When content is empty, reasoning_content is used as the answer."""
    body = {
        "choices": [{"message": {
            "content": "",
            "reasoning_content": "BEGIN_FILE calc.py\npass\nEND_FILE\n",
        }}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.content == "BEGIN_FILE calc.py\npass\nEND_FILE\n"
    assert resp.thinking == ""


def test_parse_body_content_wins_when_present():
    """When content is non-empty, it is used and reasoning_content goes to thinking."""
    body = {
        "choices": [{"message": {
            "content": "BEGIN_FILE calc.py\npass\nEND_FILE\n",
            "reasoning_content": "let me think...",
        }}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.content == "BEGIN_FILE calc.py\npass\nEND_FILE\n"
    assert resp.thinking == "let me think..."


def test_parse_body_both_empty():
    """Both content and reasoning_content absent → empty content, empty thinking."""
    body = {"choices": [{"message": {}}], "usage": {}}
    resp = _parse_body(body, _ELAPSED)
    assert resp.content == ""
    assert resp.thinking == ""


def test_parse_body_timings_used_when_present():
    """predicted_ms timing is preferred over wall time for eval_duration."""
    body = {
        "choices": [{"message": {"content": "x"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "timings": {"predicted_ms": 500.0, "prompt_ms": 100.0},
    }
    resp = _parse_body(body, _ELAPSED)
    assert resp.metrics.eval_duration == 500_000_000
    assert resp.metrics.prompt_eval_duration == 100_000_000


# ---------------------------------------------------------------------------
# Fix 2: llama-server system message differs from Ollama system message
# ---------------------------------------------------------------------------

def _capture_chat_fn(store: dict):
    """Returns a chat_fn that records kwargs and returns a correct response."""
    def chat_fn(**kwargs):
        store.update(kwargs)
        msg_len = sum(len(m.get("content", "")) for m in kwargs.get("messages", []))
        return OllamaResponse(
            content=_file_block(CORRECT_CALC),
            thinking="",
            metrics=_metrics(prompt_tokens=max(500, msg_len // 4)),
        )
    return chat_fn


def test_llama_server_system_message_starts_with_after_reasoning():
    """llama-server backend uses the 'After your reasoning,' system message."""
    captured: dict = {}
    run_one(
        model="mock-model",
        task=TASK,
        client_url="http://unused",
        num_ctx=4096,
        temperature=0.0,
        seed=1,
        num_predict=400,
        model_timeout=60,
        chat_fn=_capture_chat_fn(captured),
        backend="llama-server",
    )
    sys_msg = captured["messages"][0]["content"]
    assert sys_msg.startswith("After your reasoning,"), repr(sys_msg)


def test_ollama_system_message_does_not_mention_reasoning():
    """Ollama backend uses the original system message (no 'After your reasoning,' prefix)."""
    captured: dict = {}
    run_one(
        model="mock-model",
        task=TASK,
        client_url="http://unused",
        num_ctx=4096,
        temperature=0.0,
        seed=1,
        num_predict=400,
        model_timeout=60,
        chat_fn=_capture_chat_fn(captured),
        backend="ollama",
    )
    sys_msg = captured["messages"][0]["content"]
    assert not sys_msg.startswith("After your reasoning,"), repr(sys_msg)
    assert "BEGIN_FILE" in sys_msg
