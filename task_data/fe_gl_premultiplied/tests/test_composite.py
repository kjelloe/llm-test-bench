"""fe_gl_premultiplied: a HUD canvas composited like a browser composites a <canvas> (incidents B13/B14).

What the browser shows for canvas content C with alpha a over the page B is a*C + (1-a)*B (sRGB values, as the page
blends), with overlapping canvas content composited first. Run under xvfb-run with llvmpipe."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = (100, 140, 180)


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


def over(c, a, under):
    return tuple(a * c[i] + (1 - a) * under[i] for i in range(3))


def near(got, want, tol=3):
    return max(abs(g - w) for g, w in zip(got, want)) <= tol


def check(shots, scene, x, y, want):
    got = at(shots, scene, x, y)
    assert near(got, want), f"{scene} at ({x}, {y}): got {got}, browser shows {tuple(round(v) for v in want)}"


A_GLASS, A_ORANGE, A_GREEN = 153 / 255, 102 / 255, 128 / 255


def test_glass_panel(shots):
    check(shots, "panel", 15, 15, over((10, 20, 40), A_GLASS, B))


def test_opaque_text_on_the_panel(shots):
    check(shots, "panel", 40, 35, (255, 255, 255))


def test_translucent_orange(shots):
    check(shots, "panel", 115, 15, over((255, 80, 0), A_ORANGE, B))


def test_overlap_composited_inside_the_canvas_first(shots):
    check(shots, "panel", 150, 50, over((40, 200, 120), A_GREEN, over((255, 80, 0), A_ORANGE, B)))


def test_transparent_canvas_leaves_the_page(shots):
    check(shots, "panel", 100, 100, B)


def test_canvas_drawn_with_half_alpha(shots):
    check(shots, "faded", 15, 15, over((10, 20, 40), 0.5 * A_GLASS, B))
    check(shots, "faded", 40, 35, over((255, 255, 255), 0.5, B))


def test_scaled_down_lines_have_no_dark_halo(shots):
    want = over((255, 255, 255), 0.5, B)   # each output pixel covers one white column and one transparent one
    bad = [(x, y, at(shots, "scaled", x, y)) for y in range(5, 55, 7) for x in range(5, 95, 3)
           if not near(at(shots, "scaled", x, y), want, 4)]
    assert not bad, f"{len(bad)} probes off; e.g. ({bad[0][0]}, {bad[0][1]}) = {bad[0][2]}, browser shows {tuple(round(v) for v in want)}"
