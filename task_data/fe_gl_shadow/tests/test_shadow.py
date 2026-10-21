"""fe_gl_shadow: a directional light's shadow map (three r162's WebGLShadowMap, PCFShadowMap) on fastengine's raylib
renderer, rendered under xvfb + llvmpipe and compared with the same scenes rendered with fastengine's own shadow code
(tests/fixtures). Each region of each scene must match within 3 levels per channel on all but 1% of its pixels; the whole
frame within 3 levels on all but 0.5%."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCENES = ["noon", "evening"]
# (x0, y0, x1, y1) in the 240x160 frame
REGIONS = {
    "noon": {
        "ball_shadow": (64, 78, 92, 97),
        "crate_shadow": (94, 70, 114, 94),
        "pillar_shadow_cut_at_shadow_camera": (138, 66, 170, 86),
        "open_ground": (170, 105, 236, 156),
        "crate_and_ball_faces": (72, 58, 132, 92),
    },
    "evening": {
        "crate_shadow": (126, 76, 162, 100),
        "ball_shadow": (100, 88, 140, 108),
        "pillar_shadow": (164, 76, 208, 92),
        "open_ground": (16, 108, 92, 156),
        "crate_and_ball_faces": (72, 58, 132, 92),
    },
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
    status = dict(line.split() for line in (out / "compiled.txt").read_text().splitlines())
    assert all(status.get(s) == "compiled" for s in SCENES), f"the scene shader did not compile with Shadows.Glsl: {status}"
    return {s: read(out / f"{s}.png") for s in SCENES}


def off_pixels(got, want, box=None):
    w, h, g = got
    _, _, e = want
    x0, y0, x1, y1 = box or (0, 0, w, h)
    return [(x, y, g[y * w + x], e[y * w + x]) for y in range(y0, y1) for x in range(x0, x1)
            if max(abs(g[y * w + x][k] - e[y * w + x][k]) for k in range(3)) > 3], (x1 - x0) * (y1 - y0)


@pytest.mark.parametrize("scene,region", [(s, r) for s in SCENES for r in REGIONS[s]])
def test_region_matches_three(shots, scene, region):
    off, n = off_pixels(shots[scene], read(ROOT / "tests" / "fixtures" / f"{scene}.png"), REGIONS[scene][region])
    assert len(off) <= 0.01 * n, f"{scene} {region}: {len(off)} of {n} pixels differ; first {off[0]} (x, y, got, expected)"


@pytest.mark.parametrize("scene", SCENES)
def test_frame_matches_three(shots, scene):
    off, n = off_pixels(shots[scene], read(ROOT / "tests" / "fixtures" / f"{scene}.png"))
    assert len(off) <= 0.005 * n, f"{scene}: {len(off)} of {n} pixels differ; first {off[0]} (x, y, got, expected)"
