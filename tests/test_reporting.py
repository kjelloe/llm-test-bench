from lib.reporting import _skill_level, _peak_skill_level

# Shared task difficulty map used across tests
DIFFICULTIES = {
    "task_l1a": 1,
    "task_l2a": 2,
    "task_l3a": 3,
    "task_l3b": 3,
    "task_l4a": 4,
    "task_l5a": 5,
    "task_l5b": 5,
}
TASKS = list(DIFFICULTIES.keys())


def _rec(task: str, pass_: bool, error_kind: str = "") -> dict:
    return {"model": "m", "task": task, "tests_pass": pass_, "error_kind": error_kind}


def _idx(*recs) -> dict:
    return {("m", r["task"]): r for r in recs}


# ── _skill_level tests ────────────────────────────────────────────────────────

def test_skill_all_pass():
    idx = _idx(*[_rec(t, True) for t in TASKS])
    assert _skill_level("m", TASKS, idx, DIFFICULTIES) == "L5"


def test_skill_consecutive_wall():
    # Passes L1-L2, fails one L3 → wall at L2 even though L4/L5 pass
    idx = _idx(
        _rec("task_l1a", True),
        _rec("task_l2a", True),
        _rec("task_l3a", False),
        _rec("task_l3b", True),
        _rec("task_l4a", True),
        _rec("task_l5a", True),
        _rec("task_l5b", True),
    )
    assert _skill_level("m", TASKS, idx, DIFFICULTIES) == "L2"


def test_skill_infra_error_counts_as_pass():
    idx = _idx(
        _rec("task_l1a", True),
        _rec("task_l2a", True),
        _rec("task_l3a", False, "SKIPPED_CTX"),  # infra limit → counts as pass
        _rec("task_l3b", True),
        _rec("task_l4a", True),
        _rec("task_l5a", True),
        _rec("task_l5b", True),
    )
    assert _skill_level("m", TASKS, idx, DIFFICULTIES) == "L5"


def test_skill_no_difficulties_returns_question():
    idx = _idx(_rec("task_l1a", True))
    assert _skill_level("m", ["task_l1a"], idx, {}) == "?"


def test_skill_all_fail():
    idx = _idx(*[_rec(t, False) for t in TASKS])
    assert _skill_level("m", TASKS, idx, DIFFICULTIES) == "<L1"


# ── _peak_skill_level tests ───────────────────────────────────────────────────

def test_peak_all_pass():
    idx = _idx(*[_rec(t, True) for t in TASKS])
    assert _peak_skill_level("m", TASKS, idx, DIFFICULTIES) == "L5"


def test_peak_ignores_lower_level_failure():
    # Passes L1-L2, fails one L3, passes all L4 and L5 → Peak L5
    idx = _idx(
        _rec("task_l1a", True),
        _rec("task_l2a", True),
        _rec("task_l3a", False),   # L3 failure
        _rec("task_l3b", True),
        _rec("task_l4a", True),
        _rec("task_l5a", True),
        _rec("task_l5b", True),
    )
    assert _peak_skill_level("m", TASKS, idx, DIFFICULTIES) == "L5"


def test_peak_partial_l5_falls_back():
    # Fails one L5 task → peak is not L5; check L4 next
    idx = _idx(
        _rec("task_l1a", True),
        _rec("task_l2a", True),
        _rec("task_l3a", True),
        _rec("task_l3b", True),
        _rec("task_l4a", True),
        _rec("task_l5a", False),   # L5 incomplete
        _rec("task_l5b", True),
    )
    assert _peak_skill_level("m", TASKS, idx, DIFFICULTIES) == "L4"


def test_peak_infra_error_counts_as_pass():
    idx = _idx(
        _rec("task_l1a", True),
        _rec("task_l2a", True),
        _rec("task_l3a", False, "SKIPPED_VRAM"),  # infra → pass
        _rec("task_l3b", True),
        _rec("task_l4a", True),
        _rec("task_l5a", True),
        _rec("task_l5b", True),
    )
    assert _peak_skill_level("m", TASKS, idx, DIFFICULTIES) == "L5"


def test_peak_no_difficulties_returns_question():
    idx = _idx(_rec("task_l1a", True))
    assert _peak_skill_level("m", ["task_l1a"], idx, {}) == "?"


def test_peak_all_fail():
    idx = _idx(*[_rec(t, False) for t in TASKS])
    assert _peak_skill_level("m", TASKS, idx, DIFFICULTIES) == "<L1"


def test_peak_vs_skill_diverge():
    # The key case: Skill=L2, Peak=L5 (gemma4:31b / qwen3.6:35b-A3B pattern)
    idx = _idx(
        _rec("task_l1a", True),
        _rec("task_l2a", True),
        _rec("task_l3a", False),   # L3 wall for Skill
        _rec("task_l3b", True),
        _rec("task_l4a", True),
        _rec("task_l5a", True),
        _rec("task_l5b", True),
    )
    skill = _skill_level("m", TASKS, idx, DIFFICULTIES)
    peak  = _peak_skill_level("m", TASKS, idx, DIFFICULTIES)
    assert skill == "L2"
    assert peak  == "L5"
