"""fe_gl_nested: a mirror's reflection pass rendered from an onBeforeRender hook in the middle of a frame (fastengine spec
B16), rendered under xvfb + llvmpipe and compared with fastengine's own RenderInto (tests/fixtures) region by region,
within 3 levels per channel on all but 1% of each region's pixels. The hooks run once per frame, never in a nested pass."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
# (frame, x0, y0, x1, y1) in the 240x160 frames
REGIONS = {
    "title_bar_drawn_before_the_render": ("frame1", 0, 0, 240, 20),
    "crate": ("frame1", 38, 66, 86, 112),
    "pillar": ("frame1", 160, 22, 194, 104),
    "mirror_shows_the_reflected_scene": ("frame1", 86, 48, 154, 83),
    "mirror_projection_set_by_hand": ("frame1", 106, 62, 150, 76),
    "hud_drawn_after_the_render": ("frame1", 4, 124, 76, 156),
    "next_frame_scene": ("frame2", 90, 34, 180, 124),
    "next_frame_hud": ("frame2", 170, 4, 236, 28),
}


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


@pytest.mark.parametrize("region", REGIONS)
def test_region_matches_fastengine(shots, region):
    frame, x0, y0, x1, y1 = REGIONS[region]
    w, _, got = read(shots / f"{frame}.png")
    _, _, want = read(ROOT / "tests" / "fixtures" / f"{frame}.png")
    off = [(x, y, got[y * w + x][:3], want[y * w + x][:3]) for y in range(y0, y1) for x in range(x0, x1)
           if max(abs(got[y * w + x][k] - want[y * w + x][k]) for k in range(3)) > 3]
    n = (x1 - x0) * (y1 - y0)
    assert len(off) <= 0.01 * n, f"{region}: {len(off)} of {n} pixels differ; first {off[0]} (x, y, drew, expected)"


def test_hooks_run_once_per_frame_and_not_in_the_nested_pass(shots):
    counts = dict(line.split() for line in (shots / "hooks.txt").read_text().splitlines())
    assert counts == {"frame": "2", "nested": "0"}, (f"hook calls: {counts} (the mirror's and frame 2's once each, "
                                                     f"the reflected scene's never)")
