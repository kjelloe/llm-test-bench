# Open Ocean

A realistic ocean scene built with **Three.js** (r160). Single self-contained
`index.html` — no build step.

## Run it

Any static server works (ES modules need http, not `file://`):

```bash
cd this-directory
python3 -m http.server 8000
# open http://localhost:8000
```

Or just open `index.html` in a browser that allows module scripts from disk.

## What's in the scene

- **Water** — Three.js `Water` mirror shader: real-time planar reflection of the
  whole scene, multi-octave normal-map ripples, Schlick fresnel, sun specular
  glint, and distance fog. Uses the official `waternormals.jpg` when reachable,
  with a procedurally generated tileable normal map as an offline fallback.
- **Sky** — Three.js `Sky` (Preetham physical sky model) with a visible sun disc.
  The sky is also baked to a PMREM and used as image-based lighting for the
  PBR materials, so the island/boat are lit by the actual sky.
- **Lighting** — a directional "sun" light with soft shadows (toggleable), a
  hemisphere fill light, ACES filmic tone mapping, and sRGB output.
- **Terrain** — a displaced icosahedron island with height-based vertex colors
  (sand → rock → grass) plus two distant rocks for depth.
- **Boat** — a low-poly sailboat that bobs and rolls on the water.

## Controls

- **Drag** to orbit, **scroll** to zoom (auto-orbits until you first interact).
- **Sun elevation / azimuth** sliders move the sun; the sky, fog, light color,
  exposure, and environment map all update to match (sunset → noon).
- **Sun shadows** checkbox toggles shadow mapping.

## Notes

- Three.js is loaded from the jsDelivr CDN; the water normal map from GitHub
  (with a procedural fallback). Everything else is generated in-page.
- `preview/` contains screenshots at golden hour, noon, and sunset.
