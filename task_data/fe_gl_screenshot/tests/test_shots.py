"""fe_gl_screenshot: Shot.Capture against the same scenes rendered here at 2x and read back raw.

Run under a display (the task's test command wraps pytest in xvfb-run with Mesa's software renderer). The expected image
of each scene is its raw 2x render, flipped upright (GL stores it bottom-up) and box-filtered 2x2; Capture's PNG must
match it within 2 levels per channel at every pixel.
"""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZES = {"corners": (120, 80), "stripes": (64, 48), "diagonal": (101, 77), "solid": (40, 30), "lowmark": (40, 30)}


@pytest.fixture(scope="session")
def shots(tmp_path_factory):
    out = tmp_path_factory.mktemp("shots")
    bin_dir = tmp_path_factory.mktemp("bin")
    build = subprocess.run(["dotnet", "build", "tools/SceneRunner", "-v", "q", "-nologo", "-o", str(bin_dir)], cwd=ROOT,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-2000:]
    run = subprocess.run(["dotnet", str(bin_dir / "SceneRunner.dll"), str(out)], cwd=ROOT, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return out


def expected(raw_path):
    w2, h2, px = read(raw_path)
    upright = [px[(h2 - 1 - y) * w2 + x] for y in range(h2) for x in range(w2)]
    w, h = w2 // 2, h2 // 2
    box = []
    for y in range(h):
        for x in range(w):
            q = [upright[(2 * y + dy) * w2 + 2 * x + dx] for dy in (0, 1) for dx in (0, 1)]
            box.append(tuple(sum(c[i] for c in q) / 4 for i in range(3)))
    return w, h, box


@pytest.mark.parametrize("scene", ["corners", "stripes", "diagonal"])
def test_matches_the_supersampled_upright_render(shots, scene):
    w, h, want = expected(shots / f"{scene}-raw2x.png")
    gw, gh, got = read(shots / f"{scene}.png")
    assert (gw, gh) == SIZES[scene] == (w, h), f"{scene}: size {gw}x{gh}, expected {w}x{h}"
    bad = [(i % w, i // w, g, tuple(round(v) for v in e)) for i, (g, e) in enumerate(zip(got, want))
           if max(abs(g[k] - e[k]) for k in range(3)) > 2]
    assert not bad, f"{scene}: {len(bad)} of {w * h} pixels off, first at (x, y) {bad[0][:2]}: got {bad[0][2]}, want {bad[0][3]}"


def test_upright_red_top_left_green_bottom_right(shots):
    w, h, px = read(shots / "corners.png")
    assert px[2 * w + 2][0] > 180 and px[2 * w + 2][1] < 80, f"top-left is {px[2 * w + 2]}, expected red"
    assert px[(h - 3) * w + w - 3][1] > 160, f"bottom-right is {px[(h - 3) * w + w - 3]}, expected green"


def test_stripes_average_to_gray(shots):
    w, h, px = read(shots / "stripes.png")
    c = px[(h // 4) * w + w // 2]
    assert all(118 <= v <= 138 for v in c), f"1 px stripes at 2x should reduce to mid gray, got {c}"


def test_logs_the_path(shots):
    log = (shots / "corners.log").read_text()
    assert f"[Shot] {shots / 'corners.png'}" in log, log
    assert (shots / "corners.result").read_text() == "true"


def test_single_colour_is_reported(shots):
    assert (shots / "solid.result").read_text() == "false", "a single-colour frame must return false"
    assert "[Shot] image is a single colour" in (shots / "solid.log").read_text()


def test_a_frame_with_one_small_mark_is_not_single_colour(shots):
    assert (shots / "lowmark.result").read_text() == "true", "only the bottom rows differ; the frame is not a single colour"
