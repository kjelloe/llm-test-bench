"""lib/load_check.evaluate(): which competing work gets flagged before a benchmark run."""
from lib.load_check import evaluate


def test_flags_cpu_hogs_and_busy_gpus_only():
    procs = [
        (100, 100.0, "/work/games/boombrawl/Build/linux64/boombrawl.x86_64 -batchmode -logFile -"),
        (200, 10.0, "claude"),
        (300, 49.9, "python3 something"),
    ]
    gpus = [(0, 1509), (1, 19468), (2, 0)]
    warnings = evaluate(procs, gpus, ignore_pids=set())
    assert len(warnings) == 2
    assert warnings[0].startswith("CPU: pid 100 at 100%")
    assert "boombrawl.x86_64" in warnings[0]
    assert warnings[1] == "GPU1: 19468 MiB VRAM already in use before the run"


def test_ignores_own_process_tree_and_idle_system():
    assert evaluate([(42, 300.0, "bash ./run.sh")], [(0, 1500)], ignore_pids={42}) == []
    assert evaluate([], [], ignore_pids=set()) == []


def test_sorted_by_cpu_descending():
    procs = [(1, 60.0, "a"), (2, 250.0, "b")]
    w = evaluate(procs, [], ignore_pids=set())
    assert [line.split()[2] for line in w] == ["2", "1"]
