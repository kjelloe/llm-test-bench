"""fe_gl_mirror_target: a mirror's reflection pass and the screen pass, against three r162's arithmetic (incident B09).

Surfaces on screen show toSRGB(ACES(linear, exposure)). The mirror shows its reflection target's texel times its
reflectivity, toned and encoded once; the target is 8-bit, so what it can hold is a linear value rounded to 1/255.
Run under xvfb-run with llvmpipe."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPOSURE, REFLECT = 1.2, 0.7
WALL, CRATE = (0.18, 0.25, 0.40), (0.80, 0.45, 0.12)


def aces(c, exposure):
    c = [v * exposure / 0.6 for v in c]
    i = ((0.59719, 0.35458, 0.04823), (0.07600, 0.90834, 0.01566), (0.02840, 0.13383, 0.83777))
    o = ((1.60475, -0.53108, -0.07367), (-0.10208, 1.10813, -0.00605), (-0.00327, -0.07276, 1.07602))
    v = [sum(i[r][k] * c[k] for k in range(3)) for r in range(3)]
    v = [(x * (x + 0.0245786) - 0.000090537) / (x * (0.983729 * x + 0.4329510) + 0.238081) for x in v]
    v = [sum(o[r][k] * v[k] for k in range(3)) for r in range(3)]
    return [min(1.0, max(0.0, x)) for x in v]


def srgb(c):
    return [x * 12.92 if x <= 0.0031308 else x ** 0.41666 * 1.055 - 0.055 for x in c]


def screen(linear):
    return tuple(round(255 * x) for x in srgb(aces(linear, EXPOSURE)))


def in_target(linear):
    return [round(255 * min(1.0, x)) / 255 for x in linear]


@pytest.fixture(scope="session")
def frame(tmp_path_factory):
    out, bin_dir = tmp_path_factory.mktemp("shots"), tmp_path_factory.mktemp("bin")
    build = subprocess.run(["dotnet", "build", "tools/SceneRunner", "-v", "q", "-nologo", "-o", str(bin_dir)], cwd=ROOT,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-2000:]
    run = subprocess.run(["dotnet", str(bin_dir / "SceneRunner.dll"), str(out)], cwd=ROOT, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return read(out / "frame.png")


def check(frame, x, y, want, what):
    w, _, px = frame
    got = px[y * w + x]
    assert max(abs(g - v) for g, v in zip(got, want)) <= 3, f"{what} at ({x}, {y}): got {got}, three shows {want}"


def test_wall_on_screen(frame):
    check(frame, 30, 30, screen(WALL), "wall")


def test_crate_on_screen(frame):
    check(frame, 30, 90, screen(CRATE), "crate")


def test_mirror_shows_the_wall_toned_and_encoded_once(frame):
    check(frame, 150, 40, screen([REFLECT * v for v in in_target(WALL)]), "wall in the mirror")


def test_mirror_shows_the_crate_toned_and_encoded_once(frame):
    check(frame, 210, 40, screen([REFLECT * v for v in in_target(CRATE)]), "crate in the mirror")


def test_screen_output_is_restored_after_the_mirror_pass(frame):
    check(frame, 150, 95, screen(CRATE), "crate drawn after the mirror's pass")
