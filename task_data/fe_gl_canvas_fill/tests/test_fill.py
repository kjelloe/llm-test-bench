"""fe_gl_canvas_fill: Canvas.Fill under rlgl's back-face culling (incident A05). Run under xvfb-run with llvmpipe."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
BG = (16, 16, 16)


@pytest.fixture(scope="session")
def shots(tmp_path_factory):
    out, bin_dir = tmp_path_factory.mktemp("shots"), tmp_path_factory.mktemp("bin")
    build = subprocess.run(["dotnet", "build", "tools/SceneRunner", "-v", "q", "-nologo", "-o", str(bin_dir)], cwd=ROOT,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-2000:]
    run = subprocess.run(["dotnet", str(bin_dir / "SceneRunner.dll"), str(out)], cwd=ROOT, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return out


def at(shots, scene, x, y):
    w, _, px = read(shots / f"{scene}.png")
    return px[y * w + x]


def near(a, b, tol=6):
    return max(abs(p - q) for p, q in zip(a, b)) <= tol


def test_clockwise_square_is_filled(shots):
    assert near(at(shots, "windings", 40, 40), (220, 40, 40)), at(shots, "windings", 40, 40)


def test_anticlockwise_triangle_is_filled(shots):
    assert near(at(shots, "windings", 110, 40), (40, 80, 220)), at(shots, "windings", 110, 40)


def test_hexagons_both_windings(shots):
    assert near(at(shots, "polygons", 50, 60), (40, 200, 90)), at(shots, "polygons", 50, 60)
    assert near(at(shots, "polygons", 140, 60), (240, 200, 0)), at(shots, "polygons", 140, 60)


def test_fill_inside_culled_draws(shots):
    assert near(at(shots, "state", 110, 40), (220, 40, 40)), at(shots, "state", 110, 40)


def test_back_facing_triangle_before_the_fill_stays_culled(shots):
    assert near(at(shots, "state", 20, 20), BG), f"drawn: {at(shots, 'state', 20, 20)} (the batch was not flushed before culling went off)"


def test_back_facing_triangle_after_the_fill_stays_culled(shots):
    assert near(at(shots, "state", 170, 20), BG), f"drawn: {at(shots, 'state', 170, 20)} (culling left off after the fill)"


def test_front_facing_triangle_after_the_fill_still_draws(shots):
    assert near(at(shots, "state", 240, 20), (40, 80, 220)), at(shots, "state", 240, 20)


def test_background_untouched(shots):
    assert near(at(shots, "windings", 200, 80), BG) and near(at(shots, "state", 290, 90), BG)
