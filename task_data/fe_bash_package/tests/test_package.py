"""Drives scripts/package.sh against a fake game folder in a temp dir."""
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "package.sh"


def game(tmp_path, builds):
    g = tmp_path / "cd"
    (g / "Build").mkdir(parents=True)
    (g / "product.txt").write_text("CarrierDominion\n")
    for target, versions in builds.items():
        (g / "Build" / target / "data").mkdir(parents=True)
        (g / "Build" / target / "game.bin").write_text(target)
        (g / "Build" / target / "data" / "a.txt").write_text("a")
        (g / "Build" / f"{target}.build").write_text(
            "".join(f"[Build] version={v} target={target}\n" for v in versions) + "done\n")
    return g


def run(tmp_path, g, *args, env=None):
    return subprocess.run(["bash", str(SCRIPT), str(g), *args], cwd=tmp_path, capture_output=True, text=True,
                          timeout=60, env={**os.environ, **(env or {})})


def test_packages_each_target_with_one_top_folder(tmp_path):
    g = game(tmp_path, {"linux64": ["2026.10.12-aa-bb"], "win64": ["2026.10.12-aa-bb"]})
    r = run(tmp_path, g, "linux64", "win64")
    assert r.returncode == 0, r.stderr
    z = tmp_path / "dist" / "CarrierDominion-fe-2026.10.12-aa-bb-linux64.zip"
    names = zipfile.ZipFile(z).namelist()
    assert sorted(names) == ["CarrierDominion-fe/data/a.txt", "CarrierDominion-fe/game.bin"]
    assert (tmp_path / "dist" / "CarrierDominion-fe-2026.10.12-aa-bb-win64.zip").is_file()


def test_the_last_stamped_version_wins(tmp_path):
    g = game(tmp_path, {"linux64": ["2026.10.11-aa-bb", "2026.10.12-cc-dd"]})
    assert run(tmp_path, g, "linux64").returncode == 0
    assert (tmp_path / "dist" / "CarrierDominion-fe-2026.10.12-cc-dd-linux64.zip").is_file()


def test_takes_a_comma_list_like_build_sh(tmp_path):
    g = game(tmp_path, {"linux64": ["1-a-b"], "win64": ["1-a-b"]})
    r = run(tmp_path, g, "linux64,win64")
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in (tmp_path / "dist").iterdir()) == [
        "CarrierDominion-fe-1-a-b-linux64.zip", "CarrierDominion-fe-1-a-b-win64.zip"]


@pytest.mark.parametrize("args", [("win64",), ("linux64,win64",), ()])
def test_a_target_never_built_fails_loudly(tmp_path, args):
    g = game(tmp_path, {"linux64": ["1-a-b"]})
    r = run(tmp_path, g, *args)
    assert r.returncode == 1, f"exit {r.returncode}, stderr: {r.stderr!r}"
    assert "win64" in r.stderr and "build.sh" in r.stderr, r.stderr


def test_a_build_without_a_stamp_fails_loudly(tmp_path):
    g = game(tmp_path, {"linux64": []})
    r = run(tmp_path, g, "linux64")
    assert r.returncode == 1 and "linux64" in r.stderr, (r.returncode, r.stderr)


def test_dirty_builds_are_refused_unless_allowed(tmp_path):
    g = game(tmp_path, {"linux64": ["1-a-b-dirty"]})
    r = run(tmp_path, g, "linux64")
    assert r.returncode == 1 and "uncommitted" in r.stderr
    assert not (tmp_path / "dist" / "CarrierDominion-fe-1-a-b-dirty-linux64.zip").exists()
    assert run(tmp_path, g, "linux64", env={"ALLOW_DIRTY": "1"}).returncode == 0


def test_a_stamped_log_whose_build_folder_is_gone_fails_loudly(tmp_path):
    import shutil
    g = game(tmp_path, {"linux64": ["1-a-b"]})
    shutil.rmtree(g / "Build" / "linux64")
    r = run(tmp_path, g, "linux64")
    assert r.returncode == 1 and "linux64" in r.stderr and "build.sh" in r.stderr, (r.returncode, r.stderr)
