// Fixtures for fe_output_color: three r162 itself (js/three.reference.mjs) renders an unlit MeshBasicMaterial plane
// filling a 2×2 canvas (or render target) in headless Chromium for each case, and the pixel it wrote is read back.
// Usage: PLAYWRIGHT=/path/to/node_modules/playwright-core node tools/make_fixtures.reference.mjs > tests/FastengineTests/fixtures.json
import { createRequire } from 'module';
import { readFileSync } from 'fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT);
const three = readFileSync(new URL('../js/three.reference.mjs', import.meta.url), 'utf8');

let seed = 11;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const pick = (a) => a[Math.floor(rand() * a.length)];
const r3 = (x) => Math.round(x * 1000) / 1000;

const base = { toneMapping: 'ACESFilmic', exposure: 1, toScreen: true, toneMapped: true, materialFog: true, fog: 'none',
  fogColor: [0.5, 0.6, 0.7], fogNear: 1, fogFar: 50, fogDensity: 0.05, depth: 10 };
const cases = [
  { name: 'aces_mid', color: [0.5, 0.2, 0.05] },
  { name: 'aces_hdr', color: [2.5, 1.2, 0.6] },
  { name: 'aces_exposure', color: [0.3, 0.3, 0.3], exposure: 1.8 },
  { name: 'aces_dark_linear_segment', color: [0.002, 0.0005, 0.01] },
  { name: 'no_tone_mapping', color: [0.5, 0.2, 0.05], toneMapping: 'None' },
  { name: 'no_tone_mapping_clips', color: [1.5, 0.9, 0.001], toneMapping: 'None' },
  { name: 'linear_exposure', color: [0.4, 0.7, 0.1], toneMapping: 'Linear', exposure: 1.5 },
  { name: 'reinhard', color: [0.8, 2.0, 0.2], toneMapping: 'Reinhard', exposure: 0.8 },
  { name: 'material_not_tone_mapped', color: [0.5, 0.2, 0.05], toneMapped: false },
  { name: 'render_target_linear_untoned', color: [0.5, 0.2, 0.05], toScreen: false },
  { name: 'render_target_clamps', color: [2.0, 0.5, 0.0], toScreen: false },
  { name: 'fog_exp2_after_encoding', color: [0.1, 0.4, 0.2], fog: 'Exp2', fogDensity: 0.06, depth: 12 },
  { name: 'fog_linear_mid', color: [0.9, 0.1, 0.1], fog: 'Linear', fogNear: 5, fogFar: 25, depth: 15 },
  { name: 'fog_linear_before_near', color: [0.9, 0.1, 0.1], fog: 'Linear', fogNear: 5, fogFar: 25, depth: 3 },
  { name: 'fog_linear_past_far', color: [0.9, 0.1, 0.1], fog: 'Linear', fogNear: 5, fogFar: 25, depth: 40 },
  { name: 'fog_off_for_material', color: [0.1, 0.4, 0.2], fog: 'Exp2', materialFog: false, depth: 12 },
  { name: 'fog_in_render_target', color: [0.1, 0.4, 0.2], fog: 'Exp2', fogDensity: 0.06, depth: 12, toScreen: false },
  { name: 'fog_with_untoned_material', color: [1.4, 0.4, 0.2], fog: 'Linear', fogNear: 2, fogFar: 30, depth: 9, toneMapped: false },
];
for (let i = 0; i < 24; i++) cases.push({
  name: `seeded_${String(i).padStart(2, '0')}`,
  color: [r3(rand() * 2), r3(rand() * 1.2), r3(rand() * 0.8)],
  toneMapping: pick(['ACESFilmic', 'ACESFilmic', 'None', 'Linear', 'Reinhard']),
  exposure: pick([0.6, 1, 1, 1.4]), toScreen: rand() > 0.2, toneMapped: rand() > 0.15, materialFog: rand() > 0.15,
  fog: pick(['none', 'Exp2', 'Linear']), fogColor: [r3(rand()), r3(rand()), r3(rand())],
  fogNear: pick([1, 4]), fogFar: pick([20, 60]), fogDensity: pick([0.02, 0.05, 0.1]), depth: pick([2, 8, 15, 30]),
});

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage();
await page.route('http://fe.local/**', (r) => r.request().url().endsWith('three.mjs')
  ? r.fulfill({ contentType: 'text/javascript', body: three })
  : r.fulfill({ contentType: 'text/html', body: '<canvas id="c" width="2" height="2"></canvas><script type="module">import * as T from "./three.mjs"; window.T = T; window.ready = true;</script>' }));
await page.goto('http://fe.local/index.html');
await page.waitForFunction(() => window.ready);
const out = [];
for (const c0 of cases) {
  const c = { ...base, ...c0 };
  c.rgb = await page.evaluate((c) => {
    const T = window.T;
    const r = window.r ??= new T.WebGLRenderer({ canvas: document.getElementById('c'), preserveDrawingBuffer: true, antialias: false });
    r.toneMapping = { None: T.NoToneMapping, Linear: T.LinearToneMapping, Reinhard: T.ReinhardToneMapping, ACESFilmic: T.ACESFilmicToneMapping }[c.toneMapping];
    r.toneMappingExposure = c.exposure;
    const scene = new T.Scene();
    const fogColor = new T.Color().setRGB(...c.fogColor);
    if (c.fog === 'Exp2') scene.fog = new T.FogExp2(fogColor, c.fogDensity);
    if (c.fog === 'Linear') scene.fog = new T.Fog(fogColor, c.fogNear, c.fogFar);
    const cam = new T.PerspectiveCamera(60, 1, 0.1, 1000);
    const m = new T.MeshBasicMaterial({ toneMapped: c.toneMapped, fog: c.materialFog });
    m.color.setRGB(...c.color);
    const plane = new T.Mesh(new T.PlaneGeometry(1000, 1000), m);
    plane.position.z = -c.depth;
    scene.add(plane);
    const b = new Uint8Array(4);
    if (c.toScreen) {
      r.setRenderTarget(null);
      r.render(scene, cam);
      const gl = r.getContext();
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, b);
    } else {
      const rt = new T.WebGLRenderTarget(2, 2);
      r.setRenderTarget(rt);
      r.render(scene, cam);
      r.readRenderTargetPixels(rt, 0, 0, 1, 1, b);
      r.setRenderTarget(null);
      rt.dispose();
    }
    m.dispose(); plane.geometry.dispose();
    return [b[0], b[1], b[2]];
  }, c);
  out.push(c);
}
await browser.close();
process.stdout.write(JSON.stringify(out, null, 1) + '\n');
