import pathlib
import subprocess

ROOT = pathlib.Path(__file__).parent.parent


def test_region_totals():
    result = subprocess.run(
        ["awk", "-f", str(ROOT / "stats.awk"), str(ROOT / "sales.csv")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"awk exited {result.returncode}:\n{result.stderr}"
    lines = sorted(result.stdout.strip().splitlines())
    assert lines == [
        "east: 330.25",
        "north: 345.00",
        "west: 231.25",
    ], f"unexpected output:\n{result.stdout}"
