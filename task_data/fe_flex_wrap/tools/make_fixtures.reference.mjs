// Fixtures for fe_flex_wrap: real Chromium layout (Playwright) of a flex-wrap row for each case, every item's
// offset from the container. Usage: PLAYWRIGHT=/path/to/node_modules/playwright-core node tools/make_fixtures.reference.mjs
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT);

let seed = 7;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const pick = (a) => a[Math.floor(rand() * a.length)];

const cases = [
  { name: 'wrap_two_rows_gap_both', width: 300, rowGap: 18, columnGap: 18, justify: 'flex-start', align: 'flex-start', items: [[120, 30], [120, 30], [120, 30]] },
  { name: 'no_gap', width: 300, rowGap: 0, columnGap: 0, justify: 'flex-start', align: 'flex-start', items: [[150, 20], [150, 20], [150, 20]] },
  { name: 'exact_fit_with_gap', width: 260, rowGap: 10, columnGap: 10, justify: 'flex-start', align: 'flex-start', items: [[125, 20], [125, 20], [125, 20]] },
  { name: 'one_px_too_wide', width: 259, rowGap: 10, columnGap: 10, justify: 'flex-start', align: 'flex-start', items: [[125, 20], [125, 20]] },
  { name: 'row_gap_differs', width: 200, rowGap: 24, columnGap: 6, justify: 'flex-start', align: 'flex-start', items: [[60, 20], [60, 40], [60, 20], [60, 30], [90, 25]] },
  { name: 'center', width: 400, rowGap: 8, columnGap: 8, justify: 'center', align: 'flex-start', items: [[100, 30], [100, 30], [100, 30], [100, 30]] },
  { name: 'space_between', width: 400, rowGap: 8, columnGap: 8, justify: 'space-between', align: 'flex-start', items: [[100, 30], [100, 30], [100, 30], [100, 30]] },
  { name: 'space_between_single_on_line', width: 250, rowGap: 5, columnGap: 5, justify: 'space-between', align: 'flex-start', items: [[200, 30], [200, 30]] },
  { name: 'flex_end', width: 330, rowGap: 4, columnGap: 12, justify: 'flex-end', align: 'flex-start', items: [[90, 20], [90, 20], [90, 20], [90, 20]] },
  { name: 'align_center_in_line', width: 300, rowGap: 10, columnGap: 10, justify: 'flex-start', align: 'center', items: [[80, 20], [80, 50], [80, 30], [80, 10]] },
  { name: 'align_end_in_line', width: 300, rowGap: 10, columnGap: 10, justify: 'flex-start', align: 'flex-end', items: [[80, 20], [80, 50], [80, 30], [80, 10]] },
  { name: 'item_wider_than_container', width: 150, rowGap: 6, columnGap: 6, justify: 'flex-start', align: 'flex-start', items: [[60, 20], [200, 30], [60, 20]] },
  { name: 'fractional_sizes', width: 301.5, rowGap: 7.5, columnGap: 3.25, justify: 'center', align: 'center', items: [[99.5, 21.25], [99.5, 30.5], [99.5, 12.75], [50.25, 40]] },
];
for (let i = 0; i < 10; i++) {
  const n = 3 + Math.floor(rand() * 8);
  cases.push({
    name: `seeded_${i}`, width: 180 + Math.floor(rand() * 320), rowGap: pick([0, 4, 8, 12, 18]), columnGap: pick([0, 4, 8, 12, 18]),
    justify: pick(['flex-start', 'center', 'space-between', 'flex-end']), align: pick(['flex-start', 'center', 'flex-end']),
    items: Array.from({ length: n }, () => [20 + Math.floor(rand() * 140), 10 + Math.floor(rand() * 50)]),
  });
}

const browser = await chromium.launch();
const page = await browser.newPage();
const out = [];
for (const c of cases) {
  const html = `<div id="c" style="display:flex;flex-direction:row;flex-wrap:wrap;width:${c.width}px;row-gap:${c.rowGap}px;column-gap:${c.columnGap}px;justify-content:${c.justify};align-items:${c.align};margin:0;padding:0;position:absolute;left:0;top:0">`
    + c.items.map(([w, h]) => `<div style="flex:none;width:${w}px;height:${h}px;margin:0"></div>`).join('') + '</div>';
  await page.setContent(`<!doctype html><body style="margin:0">${html}</body>`);
  const pos = await page.evaluate(() => [...document.getElementById('c').children].map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y]; }));
  out.push({ ...c, positions: pos });
}
await browser.close();
process.stdout.write(JSON.stringify(out) + '\n');
