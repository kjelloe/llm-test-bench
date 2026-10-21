"""fe_gl_lambert: MeshLambertMaterial with three r162's physical light units under GLSL 330 (spec B03).

Each quad is lit by its own lights; its centre must show what three r162 draws (NoToneMapping, sRGB output):
colours (material and lights) decoded from sRGB, irradiance = ambient + hemisphere mix(ground, sky, n.y/2 + 1/2)
+ sum of colour * intensity * max(dot(n, L), 0) with L towards the light, diffuse = irradiance * albedo / pi
(BRDF_Lambert; no legacy * pi), clamped and sRGB-encoded. Run under xvfb-run with llvmpipe."""
import json
import math
import pathlib
import subprocess

import pytest

from pngread import read

ROOT = pathlib.Path(__file__).resolve().parent.parent


def to_linear(channel):
    c = channel / 255
    return c * 0.0773993808 if c < 0.04045 else (c * 0.9478672986 + 0.0521327014) ** 2.4


def linear(hex_):
    return [to_linear((hex_ >> s) & 255) for s in (16, 8, 0)]


def to_srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def three(scene):
    n = unit(scene["normal"])
    irradiance = [0.0, 0.0, 0.0]
    for light in scene["lights"]:
        colour = [c * light["intensity"] for c in linear(light["hex"])]
        if light["kind"] == "ambient":
            add = colour
        elif light["kind"] == "hemisphere":
            ground = [c * light["intensity"] for c in linear(light["ground"])]
            w = n[1] * 0.5 + 0.5
            add = [g + (s - g) * w for s, g in zip(colour, ground)]
        else:
            to_light = unit([p - t for p, t in zip(light["position"], light["target"])])
            d = max(sum(a * b for a, b in zip(n, to_light)), 0.0)
            add = [c * d for c in colour]
        irradiance = [a + b for a, b in zip(irradiance, add)]
    out = [i * a / math.pi for i, a in zip(irradiance, linear(scene["material"]))]
    return tuple(round(255 * to_srgb(min(1.0, max(0.0, c)))) for c in out)


@pytest.fixture(scope="session")
def shot(tmp_path_factory):
    out, bin_dir = tmp_path_factory.mktemp("shots"), tmp_path_factory.mktemp("bin")
    build = subprocess.run(["dotnet", "build", "tools/SceneRunner", "-v", "q", "-nologo", "-o", str(bin_dir)], cwd=ROOT,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert build.returncode == 0, build.stdout[-4000:] + build.stderr[-2000:]
    run = subprocess.run(["dotnet", str(bin_dir / "SceneRunner.dll"), str(out)], cwd=ROOT, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    return read(out / "frame.png"), json.loads((out / "scenes.json").read_text())


NAMES = ["ambient_only", "ambient_tinted", "sun_overhead", "sun_slanted", "sun_target_off_origin", "sun_behind_surface",
         "two_suns", "hemi_facing_up", "hemi_facing_down", "hemi_sideways", "hemi_tilted", "hemi_plus_sun",
         "carrier_deck", "carrier_hull_side", "dark_material", "near_black", "overexposed_clamps", "dim_red",
         "unnormalised_normal", "four_suns"]


@pytest.mark.parametrize("name", NAMES)
def test_quad_matches_three(shot, name):
    (w, _, px), scenes = shot
    cell, columns = scenes["cell"], scenes["columns"]
    index = [s["name"] for s in scenes["scenes"]].index(name)
    scene = scenes["scenes"][index]
    x, y = index % columns * cell + cell // 2, index // columns * cell + cell // 2
    got, want = px[y * w + x][:3], three(scene)
    assert max(abs(g - v) for g, v in zip(got, want)) <= 1, f"{name}: drew {tuple(got)}, three r162 draws {want}"
