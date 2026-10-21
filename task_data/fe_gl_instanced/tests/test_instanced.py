"""fe_gl_instanced: three's InstancedBufferGeometry on raylib (fastengine spec B15), rendered under xvfb + llvmpipe.

Each scene is one mesh from Instancing.Build drawn with one DrawMesh. "palette": 12 quads whose colour and position are
two per-instance attributes; "cells": 20,000 2x2 px quads (80,000 vertices, past raylib's 16-bit indices), colour from
the instance's cell; "rain": CarrierDominion's real rain shader and drops, against fastengine's own instancing
(tests/fixtures/rain.png) within 3 levels on all but 0.5% of the pixels."""
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCENES = ["palette", "cells", "rain"]


@pytest.fixture(scope="session")
def shots(tmp_path_factory):
    out, bin_dir = tmp_path_factory.mktemp("shots"), tmp_path_factory.mktemp("bin")
    build = subprocess.run(["dotnet", "build", "tools/SceneRunner", "-v", "q", "-nologo", "-o", str(bin_dir)], cwd=ROOT,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-2000:]
    run = subprocess.run(["dotnet", str(bin_dir / "SceneRunner.dll"), str(out)], cwd=ROOT, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL, timeout=180)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return out


def compiled(shots, scene):
    status = dict(line.split() for line in (shots / "compiled.txt").read_text().splitlines())
    assert status.get(scene) == "compiled", f"{scene}: the shader did not compile (raylib used its default shader)"


def pixel(img, x, y):
    w, _, px = img
    return px[y * w + x][:3]


def near(got, want, tol=1):
    return max(abs(g - v) for g, v in zip(got, want)) <= tol


@pytest.mark.parametrize("scene", SCENES)
def test_shaders_compile(shots, scene):
    compiled(shots, scene)


@pytest.mark.parametrize("k", range(12))
def test_palette_instance_has_its_own_colour_and_place(shots, k):
    img = read(shots / "palette.png")
    want = (round(255 * (k % 4 + 1) / 5), round(255 * (k // 4 + 1) / 4), round(255 * (k * 7 % 12) / 11))
    x, y = 20 + 40 * (k % 4), 20 + 40 * (k // 4)
    for dx, dy in ((0, 0), (-4, -4), (4, 4)):
        got = pixel(img, x + dx, y + dy)
        assert near(got, want), f"instance {k} at ({x + dx}, {y + dy}): drew {tuple(got)}, its attributes give {want}"
    assert near(pixel(img, x + 10, y), (0, 0, 0)), f"instance {k}: the quad is wider than 12 px"


def cell_colour(x, y):
    return (round(255 * x / 200), round(255 * y / 100), 128)


@pytest.mark.parametrize("rows", [(0, 10), (10, 82), (82, 100)], ids=["first_instances", "middle", "past_16_bit_indices"])
def test_cells_every_instance_lands_on_its_pixel(shots, rows):
    img = read(shots / "cells.png")
    bad = [(x, y, tuple(pixel(img, x, y))) for y in range(rows[0] * 2, rows[1] * 2) for x in range(400)
           if not near(pixel(img, x, y), cell_colour(x // 2, y // 2))]
    assert not bad, (f"{len(bad)} pixels wrong; first {bad[0]} (x, y, drew), its cell's colour is "
                     f"{cell_colour(bad[0][0] // 2, bad[0][1] // 2)}")


def test_rain_matches_fastengine(shots):
    w, h, want = read(ROOT / "tests" / "fixtures" / "rain.png")
    gw, gh, got = read(shots / "rain.png")
    assert (gw, gh) == (w, h)
    off = [i for i, (g, e) in enumerate(zip(got, want)) if max(abs(g[k] - e[k]) for k in range(3)) > 3]
    assert len(off) <= 0.005 * w * h, (f"rain: {len(off)} of {w * h} pixels differ by more than 3; first at "
                                       f"({off[0] % w}, {off[0] // w}): got {got[off[0]]}, expected {want[off[0]]}")
