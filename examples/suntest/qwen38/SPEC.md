# SPEC — "Open Ocean" Three.js scene

Reproducible build spec for the ocean scene in `index.html`. Written so another
agent can rebuild it from scratch (or audit the existing file) without guessing.
The shipped `index.html` is the reference implementation; this document explains
every decision and the non-obvious API facts that cost real debugging time.

---

## 1. Overview

A single-file, no-build WebGL scene:

- Physically-based sky (Preetham model) with a visible sun disc
- Mirror-reflection water with animated ripples, fresnel, sun glint, fog
- A rocky island + 2 distant rocks (procedural geometry, vertex colors)
- A bobbing low-poly sailboat
- Dynamic sun (elevation/azimuth sliders) driving sky, fog, lights, exposure,
  and an image-based-lighting environment map
- Soft shadows, ACES tone mapping, orbit controls

**Stack:** Three.js **r160** (pinned) via ES-module import map from jsDelivr.
No bundler, no build step. One external texture (water normals) with a
procedural fallback.

## 2. File layout

```
index.html          # the entire scene (HTML + CSS + one <script type="module">)
README.md           # user-facing docs
preview/            # reference screenshots: golden-hour.png, noon.png, sunset.png
```

## 3. Dependencies

| What | Source | Notes |
|---|---|---|
| `three` | `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js` | pinned via import map |
| `three/addons/` | `https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/` | OrbitControls, Sky, Water, BufferGeometryUtils |
| `waternormals.jpg` | `https://raw.githubusercontent.com/mrdoob/three.js/r160/examples/textures/waternormals.jpg` | **NOT on jsDelivr** — the npm package omits `examples/textures/`. Use GitHub raw. Fallback: procedural canvas normal map (see §6.3) |

Import map:

```html
<script type="importmap">
{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
} }
</script>
```

## 4. Renderer / scene / camera

```js
renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;   // see §8.1 — exposure is critical
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

scene.fog = new THREE.Fog(0xbcd6e4, 150, 2000);       // MUST exist before Water is built (§6.2)

camera = new THREE.PerspectiveCamera(55, aspect, 1, 20000);  // far 20000: sky box is ±5000
camera.position.set(0, 12, 60);

controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 8, -120);          // look at the island
controls.enableDamping = true; controls.dampingFactor = 0.06;
controls.minDistance = 5; controls.maxDistance = 600;
controls.maxPolarAngle = Math.PI / 2 - 0.04;  // never dip below the water plane
controls.autoRotate = true; controls.autoRotateSpeed = 0.35;
// disable autoRotate on first pointerdown ({ once: true })
```

Scene graph:

```
scene
├── sky            (Sky, scale 10000)
├── water          (Water, PlaneGeometry 10000×10000, rotated -π/2, y=0)
├── dirLight       (sun; position = sunDir × 500; target = origin)
├── hemi           (HemisphereLight 0xbfd9e6 / 0x0a1a24)
├── island         (y=-4, z=-170, scale 35)
├── rock A         (y=-6, z=-420, x=-260, scale 16)
├── rock B         (y=-7, z=-380, x=300,  scale 22)
└── boat           (30, 0, -75, rotY -0.65)
```

Water plane is 10000×10000 (same as the official example): its edge is ~5000
units away, far beyond `fog.far = 2000`, so the horizon is always fog, never a
visible plane edge.

## 5. Sky

```js
sky = new Sky(); sky.scale.setScalar(10000); scene.add(sky);
skyU = sky.material.uniforms;
skyU['turbidity'].value      = 10;   // base; modulated by sun elevation (§8)
skyU['rayleigh'].value       = 2;    // keep constant — see §8.2
skyU['mieCoefficient'].value = 0.005;
skyU['mieDirectionalG'].value = 0.8;
```

**Non-obvious fact:** the Sky vertex shader ends with
`gl_Position.z = gl_Position.w;` — it forces its depth to the far plane, so the
sky renders even though the box (±5000) is outside the PMREM camera's default
`far = 100`. This is why `PMREMGenerator.fromScene()` works on it with default
args.

### 5.1 Environment map (IBL)

The sky is baked to a PMREM and assigned to `scene.environment` so the
`MeshStandardMaterial`s (island, boat) get sky-based ambient light:

```js
pmremGenerator = new THREE.PMREMGenerator(renderer);
function updateEnvironment() {
  if (envRT) envRT.dispose();
  const envScene = new THREE.Scene();
  envScene.add(sky);                 // move sky out of main scene
  envRT = pmremGenerator.fromScene(envScene);
  scene.add(sky);                    // move it back
  scene.environment = envRT.texture;
}
```

**Throttle it.** `fromScene` renders 6 cube faces + mips. Slider `input` events
fire many times per second, so set an `envDirty = true` flag in `updateSun()`
and regenerate **at most once per frame** in the animation loop.

## 6. Water

### 6.1 Which Water? (version gotcha)

In **r160** `three/addons/objects/Water.js` is the **mirror-based** water
(descended from the "flat mirror" work): its `onBeforeRender` renders the whole
scene from a reflected camera into a 512×512 `WebGLRenderTarget`, and the
fragment shader samples that with normal-map distortion.

Consequences:

- **No CubeCamera needed.** Reflections are automatic; the island/boat/sky all
  appear in the water for free.
- The reflection is 512×512 → intentionally soft.
- `water.material.uniforms['eye']` is set automatically from the camera in
  `onBeforeRender` — don't touch it.
- The material has `lights: true` and includes the shadow chunks, so the
  island's shadow map **automatically falls on the water** via
  `getShadowMask()` (no extra work).
- Do not confuse with the older cubemap-based Water (which had a `mirror`
  uniform). r160 has no `mirror` uniform.

### 6.2 Construction

```js
scene.fog = new THREE.Fog(...);        // must exist first
water = new Water(new THREE.PlaneGeometry(10000, 10000), {
  textureWidth: 512, textureHeight: 512,
  waterNormals: createWaterNormalsTexture(),   // procedural fallback, upgraded later
  sunDirection: sun.clone(),
  sunColor: 0xffffff,
  waterColor: 0x001e0f,        // deep blue-green (official example value)
  distortionScale: 3.7,        // official example value
  fog: true                    // enables USE_FOG in the shader
});
water.rotation.x = -Math.PI / 2;
scene.add(water);
water.material.uniforms['size'].value = 6;   // ripple scale, see below
```

- `fog: true` sets `material.fog = true`, so the renderer's `refreshFog` keeps
  the water's `fogColor/fogNear/fogFar` uniforms in sync with `scene.fog` every
  frame. Changing `scene.fog.color` at runtime (sun updates) just works.
- `size` uniform: the shader samples the normal map at
  `worldPosition.xz * size / {103, 107, 8907, 1091}` (4 octaves). `size = 6`
  → dominant ripples repeat every ~17 world units. `1` (default) is very calm;
  `10` is choppy. Tune to taste.
- `water.material.uniforms['time'].value = t` every frame drives the ripple
  drift.

### 6.3 Normal map

Primary: official `waternormals.jpg` (1024², tangent-space, 0.5 = flat),
`wrapS = wrapT = RepeatWrapping`, loaded async and swapped into
`uniforms['normalSampler']` on success.

Fallback (generated so the scene works offline): a **tileable** normal map from
a sum of sines with **integer frequencies** (integer freqs over [0,1)² tile
perfectly):

```js
// 26 waves: fx,fy ∈ integers [-12,12], amp = 1/(1+0.35·i), random phase
H[u,v] = Σ amp·sin(2π(fx·u + fy·v) + ph)
// finite differences over the height field, then normalize slopes so
// max|slope| = 0.55 (keeps the map in the same "mostly flat" range as the
// official texture), encode n = normalize(-dx·k, -dy·k, 1) → RGB = n·0.5+0.5
```

The shader does `noise = tex·0.5 - 1` then `normalize(noise.xzy · (1.5,1,1.5))`,
so standard tangent-space encoding (R=x, G=y, B=z, blue≈up) is exactly right.

## 7. Terrain & boat

### 7.1 Island (procedural rock)

```js
geo = new THREE.IcosahedronGeometry(1, 5);      // non-indexed, 20480 tris
// per vertex (n = normalized position):
h = 0.55·sin(2.7nx+p0)sin(3.1ny+p1)sin(2.3nz+p2)
  + 0.30·sin(6.1nx+p3)sin(5.3ny+p4)sin(6.7nz+p5)
  + 0.15·sin(11.3nx+p6)sin(12.7ny+p7)sin(10.9nz+p8)
  + 0.07·sin(23.1nx+p9)sin(21.7ny+p10)sin(25.3nz+p11)
r = max(1 + 0.5·h, 0.25);  v = n·r;  v.y *= 0.72;   // flatten vertically
```

- `p0..p11` are random phases from a **seeded PRNG** (`mulberry32(seed)`) so
  each rock is different but deterministic.
- **Vertex colors by local height** (before scaling): `y<0.12` sand `0xd8c493`;
  `0.12–0.5` sand→rock `0x5c6470` lerp; above → rock→grass `0x4f6b3a` lerp
  (grass amount is a per-rock parameter; distant rocks get less).
- Because the geometry is non-indexed, call
  `mergeVertices(geo, 1e-4)` (from `BufferGeometryUtils`) **then**
  `computeVertexNormals()` to get smooth shading. (Colors are a pure function
  of position, so merging is safe.)
- Material: `MeshStandardMaterial({ vertexColors: true, roughness: 0.95,
  metalness: 0 })`. `castShadow = receiveShadow = true`.
- Main island: scale 35 at (0, −4, −170) → waterline cuts through the sand band
  (local y 0.12·35 ≈ 4.2 → world ≈ 0.2).

### 7.2 Boat

`THREE.Group` of primitives: box hull (3.4×0.8×1.3, wood `0x7a4a2b`), 4-sided
cone bow (rotated −π/2 z, π/4 y, z-scaled 0.55), box stern, box cabin
(`0xf2ead8`), cylinder mast, and a **single-triangle sail** (BufferGeometry,
`DoubleSide`, `0xfaf6ec`). All meshes `castShadow = true`.

Bobbing (water surface is geometrically flat — the shader only perturbs
normals — so plain sines are the right approximation):

```js
boat.position.y = sin(t·0.8)·0.3 + sin(t·0.47+1.3)·0.18;
boat.rotation.z = sin(t·0.6+0.8)·0.05;
boat.rotation.x = sin(t·0.5+2.0)·0.035;
```

## 8. Sun model & lighting

### 8.1 Sun direction

```js
phi   = degToRad(90 - elevation);
theta = degToRad(azimuth);
sun.setFromSphericalCoords(1, phi, theta);
skyU['sunPosition'].value.copy(sun);
water.material.uniforms['sunDirection'].value.copy(sun).normalize();
dirLight.position.copy(sun).multiplyScalar(500);
```

### 8.2 Parameter curves (all keyed on `t = smoothstep(elevation, 0, 30)`)

| Parameter | Curve | Why |
|---|---|---|
| `dirLight.color` | lerp `0xff8f3d` → `0xfff2df` | warm low sun |
| `dirLight.intensity` | `1.5 + 2.0t` | |
| `hemi.intensity` | `0.3 + 0.45t` | |
| `scene.fog.color` | lerp `0xe8a87c` → `0xbcd6e4` | warm haze at sunset |
| `skyU.turbidity` | `10 − 4t` | less haze at high sun |
| `skyU.rayleigh` | **constant 2.0** | see below |
| `toneMappingExposure` | **`0.5 − 0.2t`** | **the critical one — see below** |

**The exposure curve is inverted on purpose.** The Sky shader emits physically
bright radiance; ACES desaturates highlights toward white. Measured in a
headless render: at exposure 0.55 the zenith was gray (B−R ≈ +13); at 0.30 it
was properly blue (B−R ≈ +30). Raising exposure as the sun rises (the naive
choice) makes the day sky *whiter*, not brighter-looking. So exposure must
**decrease** with elevation: 0.5 at the horizon (lets the warm glow through),
0.30 at high sun (preserves blue).

**Counterintuitive:** raising `rayleigh` did *not* make the sky bluer — it made
it brighter, which pushed it back into the white-clipping region (B−R dropped
from +21 to +10). Exposure is the dominant lever; keep rayleigh at the
official 2.0.

### 8.3 Shadows

```js
dirLight.castShadow = true;
dirLight.shadow.mapSize.set(2048, 2048);
dirLight.shadow.camera = { near: 50, far: 1200, left/right/top/bottom: ±280 };
dirLight.shadow.bias = -0.0002;
dirLight.shadow.normalBias = 3;      // low-poly island needs a big normal bias
```

- The ortho box (±280) covers island + boat + nearby water from any sun angle
  (light sits at `sun × 500`).
- The water shader samples the shadow map itself (`getShadowMask()`), so the
  island's shadow appears on the water with no extra setup.
- UI toggle: set `renderer.shadowMap.enabled` **and** `dirLight.castShadow`,
  then `material.needsUpdate = true` on all meshes (program cache key changes).

## 9. UI / chrome

- Top-left title, bottom-left glass panel (sliders: elevation 0–80 default
  **12°**, azimuth 0–360 default **205°**; shadows checkbox), bottom-right
  hint, CSS radial-gradient vignette overlay (`pointer-events: none`).
- Inline SVG data-URI favicon (🌊) — avoids a favicon 404 in console.
- Slider `input` → `updateSun()` (cheap) + `envDirty = true` (PMREM deferred
  to next frame).
- Default view: golden hour (12°/205°) — the most photogenic; sun sits behind
  the island with a specular glint path toward the camera.

## 10. Animation loop

```js
t = clock.getElapsedTime();
if (envDirty) { updateEnvironment(); envDirty = false; }
water.material.uniforms['time'].value = t;
// boat bobbing (§7.2)
controls.update();
renderer.render(scene, camera);
```

Resize handler: update aspect + `renderer.setSize`.

## 11. Verification (how to test without a human)

The scene was verified in **headless Chromium (SwiftShader)** via Playwright:

```bash
npm i playwright@1.49.0
npx playwright install chromium --only-shell
# launch args: --use-angle=swiftshader --enable-unsafe-swiftshader --no-sandbox
```

Serve the directory over http (ES modules don't run from `file://`), load the
page, then:

1. **Console/pageerror capture** — must be empty (a favicon 404 counts as a
   failure; that's why the inline favicon exists).
2. **Pixel analysis** (Pillow):
   - Zenith blueness: mean `B − R` over a top-center patch. Target ≥ +20 in
     day, warm (negative) near the horizon at sunset.
   - Water texture: variance over the bottom quarter. A flat color (var ≈ 0)
     means the normal map / reflection pipeline is broken; expect ~2000–4000.
   - Island presence: a distinct darker patch above the horizon line.
   - Sun disc: brightest pixel in the upper half, near the expected azimuth.
3. **Differential test:** render the official `webgl_shaders_ocean.html`
   (r160, from GitHub) in the same browser at the same sun parameters. If your
   sky/water pixels diverge wildly, your setup is wrong; if they match, the
   look is "as intended" and only tuning is needed. (This comparison is what
   isolated the exposure bug: the official example at 14° elevation is equally
   washed out at exposure 0.5.)

Reference numbers from the shipped scene (1280×800, headless):

| Preset | zenith (B−R) | horizon (B−R) | water mean |
|---|---|---|---|
| golden hour (12°/205°) | (179,193,200) +21 | (87,92,82) −5 | (103,112,114) |
| noon (55°/160°) | (181,197,207) +26 | (111,119,110) −1 | (94,96,97) |
| sunset (1°/205°) | (111,132,142) +31 | (40,40,33) −7 | (69,81,86) |

## 12. Gotchas checklist (things that will bite you)

1. **r160 Water is mirror-based**, not cubemap-based. No `mirror` uniform, no
   CubeCamera. `onBeforeRender` does the reflection pass.
2. **`scene.fog` must exist before `new Water(...)`** if you want `fog: true`
   to mean anything (the `fog` option is captured at construction).
3. **jsDelivr's three npm package has no `examples/textures/`** → 404 on
   `waternormals.jpg`. Use `raw.githubusercontent.com/mrdoob/three.js/r160/...`
   or rely on the procedural fallback.
4. **Exposure must decrease as the sun rises** (§8.2). This is the single
   biggest visual quality lever.
5. **PMREM regeneration is expensive** — throttle to once per frame via a
   dirty flag; dispose the old render target.
6. **`mergeVertices` before `computeVertexNormals`** for smooth shading on the
   non-indexed icosahedron.
7. **`maxPolarAngle < π/2`** or the camera can go under the (single-sided)
   water plane and see nothing.
8. **Shadow toggle needs `material.needsUpdate`** on all meshes.
9. Headless env quirk (this machine): `npx playwright install chromium
   --only-shell` left an incomplete extraction (only `icudtl.dat`). Fix:
   download the zip from
   `https://cdn.playwright.dev/builds/chromium/1148/chromium-headless-shell-linux.zip`
   and extract it manually into
   `~/.cache/ms-playwright/chromium_headless_shell-1148/`.

## 13. Run

```bash
cd this-directory
python3 -m http.server 8000
# → http://localhost:8000
```
