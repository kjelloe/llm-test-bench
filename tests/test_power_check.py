from lib.power_check import evaluate


def test_fewer_than_min_gpus_always_safe():
    # Uncapped 2-GPU (would fail the budget check) is fine — this check targets
    # the tight-headroom 3+ GPU case only.
    is_safe, msg = evaluate([450.0, 350.0], [450.0, 350.0], max_psu_watt=500, system_overhead_watt=175)
    assert is_safe
    assert msg == ""


def test_capped_within_budget_is_safe():
    is_safe, msg = evaluate([260.0, 240.0, 240.0], [450.0, 450.0, 366.0],
                             max_psu_watt=1200, system_overhead_watt=175)
    assert is_safe
    assert msg == ""


def test_uncapped_gpu_is_unsafe_even_within_budget():
    # One GPU sitting at its hardware max is a signal limits were never set/reset,
    # regardless of whether the current sum happens to fit the budget.
    is_safe, msg = evaluate([260.0, 240.0, 366.0], [450.0, 450.0, 366.0],
                             max_psu_watt=1200, system_overhead_watt=175)
    assert not is_safe
    assert "hardware power maximum" in msg


def test_capped_but_over_budget_is_unsafe():
    is_safe, msg = evaluate([260.0, 240.0, 240.0], [450.0, 450.0, 366.0],
                             max_psu_watt=500, system_overhead_watt=175)
    assert not is_safe
    assert "740W" in msg
    assert "325W" in msg


def test_message_mentions_remediation():
    _, msg = evaluate([450.0, 420.0, 350.0], [450.0, 420.0, 350.0],
                       max_psu_watt=1200, system_overhead_watt=175)
    assert "powerlimit.sh" in msg
    assert "MAX_PSU_WATT" in msg
    assert "SKIP_POWER_CHECK" in msg


def test_min_gpus_is_configurable():
    is_safe, _ = evaluate([450.0, 420.0], [450.0, 420.0],
                           max_psu_watt=500, system_overhead_watt=175, min_gpus=2)
    assert not is_safe
