"""fe_gl_shader_port: CarrierDominion's real three.js shaders ported with Fastengine.ShaderPort, rendered under xvfb +
llvmpipe, against the same scenes rendered with fastengine's own port (tests/fixtures). Each scene: the shaders compile
(raylib silently falls back to its default shader otherwise), and the image matches within 3 levels per channel on all but
0.5% of the pixels."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCENES = ["ocean", "ocean-detail", "beam"]


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


@pytest.mark.parametrize("scene", SCENES)
def test_shaders_compile(shots, scene):
    status = dict(line.split() for line in (shots / "compiled.txt").read_text().splitlines())
    assert status.get(scene) == "compiled", f"{scene}: the ported shader did not compile (raylib used its default shader)"


@pytest.mark.parametrize("scene", SCENES)
def test_scene_matches_fastengine(shots, scene):
    w, h, want = read(ROOT / "tests" / "fixtures" / f"{scene}.png")
    gw, gh, got = read(shots / f"{scene}.png")
    assert (gw, gh) == (w, h)
    off = [i for i, (g, e) in enumerate(zip(got, want)) if max(abs(g[k] - e[k]) for k in range(3)) > 3]
    assert len(off) <= 0.005 * w * h, (f"{scene}: {len(off)} of {w * h} pixels differ by more than 3; first at "
                                       f"({off[0] % w}, {off[0] // w}): got {got[off[0]]}, expected {want[off[0]]}")
