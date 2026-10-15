// Fixtures for cs_css_alpha_linear: what Chromium actually draws for a CSS rgba() panel over an opaque backdrop,
// read back from a screenshot, plus the exact linear-light blend a Linear Unity project would draw.
// Usage: PLAYWRIGHT=/path/to/node_modules/playwright-core node tools/make_fixtures.reference.mjs > tests/GameClientTests/fixtures.json
import { createRequire } from 'module';
import zlib from 'zlib';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT);

const toLin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const toSrgb = (l) => { const v = l <= 0.0031308 ? l * 12.92 : 1.055 * Math.pow(l, 1 / 2.4) - 0.055; return Math.round(Math.min(1, Math.max(0, v)) * 255); };

// HUD panels and chips from the games (dark glass panels, white chips, coloured warnings) over typical scene colours.
const overlays = [
  [[0, 0, 0], [0.1, 0.25, 0.35, 0.5, 0.65, 0.8]],
  [[10, 20, 40], [0.55, 0.65, 0.85]],
  [[255, 255, 255], [0.06, 0.12, 0.2, 0.35, 0.5, 0.7]],
  [[255, 80, 0], [0.3, 0.5]],
  [[40, 200, 120], [0.25, 0.6]],
  [[128, 128, 128], [0.5]],
];
const backdrops = [[0, 0, 0], [20, 30, 50], [70, 110, 160], [128, 128, 128], [200, 210, 220], [255, 255, 255], [34, 120, 60], [180, 40, 40]];
const cases = [];
for (const [rgb, alphas] of overlays) for (const a of alphas) for (const bd of backdrops) cases.push({ css: rgb, alpha: a, backdrop: bd });

const S = 4, COLS = 32;
const html = cases.map((c, i) => {
  const x = (i % COLS) * S, y = Math.floor(i / COLS) * S;
  return `<div style="position:absolute;left:${x}px;top:${y}px;width:${S}px;height:${S}px;background:rgb(${c.backdrop})">`
    + `<div style="width:100%;height:100%;background:rgba(${c.css},${c.alpha})"></div></div>`;
}).join('');
const browser = await chromium.launch({ args: ['--force-color-profile=srgb'] });
const page = await browser.newPage({ viewport: { width: COLS * S, height: Math.ceil(cases.length / COLS) * S }, deviceScaleFactor: 1 });
await page.setContent(`<!doctype html><body style="margin:0">${html}</body>`);
const png = await page.screenshot({ omitBackground: false });
await browser.close();

// Minimal PNG decoder (8-bit RGB/RGBA, non-interlaced), enough for Chromium's screenshot.
function decode(buf) {
  let pos = 8, width, height, ctype, idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos), type = buf.toString('latin1', pos + 4, pos + 8), data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') { width = data.readUInt32BE(0); height = data.readUInt32BE(4); ctype = data[9]; }
    if (type === 'IDAT') idat.push(data);
    pos += 12 + len;
  }
  const bpp = ctype === 6 ? 4 : 3, raw = zlib.inflateSync(Buffer.concat(idat)), stride = width * bpp;
  const out = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y++) {
    const f = raw[y * (stride + 1)], line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? out[y * stride + x - bpp] : 0, b = y > 0 ? out[(y - 1) * stride + x] : 0, c = x >= bpp && y > 0 ? out[(y - 1) * stride + x - bpp] : 0;
      let v = line[x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      out[y * stride + x] = v & 255;
    }
  }
  return { width, bpp, px: (x, y) => [0, 1, 2].map(k => out[y * stride + x * bpp + k]) };
}
const img = decode(png);
const rows = cases.map((c, i) => {
  const browser = img.px((i % COLS) * S + 1, Math.floor(i / COLS) * S + 1);
  const linear = [0, 1, 2].map(k => toSrgb(c.alpha * toLin(c.css[k]) + (1 - c.alpha) * toLin(c.backdrop[k])));
  return { css: c.css, alpha: c.alpha, backdrop: c.backdrop, browser, linear };
});
process.stdout.write(JSON.stringify(rows) + '\n');
