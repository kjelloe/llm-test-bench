"""lib/gpu_monitor.StallClock: when an open request counts as hung (every GPU idle for stall_s)."""
import json

from lib.gpu_monitor import StallClock
from lib.statistics import load_file


def test_fires_only_after_continuous_idle():
    c = StallClock(300)
    assert not c.update(0, 0)
    assert not c.update(299, 1)        # 1% still counts as idle
    assert c.update(300, 0)


def test_any_activity_or_unreadable_sample_resets():
    c = StallClock(300)
    c.update(0, 0)
    assert not c.update(200, 30)       # prompt processing, CPU-paged experts: GPU busy
    assert not c.update(450, 0)
    assert not c.update(600, None)     # unreadable sample: never kill on missing data
    assert not c.update(800, 0)
    assert c.update(1100, 0)


def test_statistics_leaves_stalled_records_out(tmp_path):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"results": [{"task": "a", "tests_pass": False, "stalled": True},
                                         {"task": "b", "tests_pass": True}]}))
    results, _ = load_file(f)
    assert [r["task"] for r in results] == ["b"]
