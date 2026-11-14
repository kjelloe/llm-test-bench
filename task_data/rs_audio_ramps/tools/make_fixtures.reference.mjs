// Fixtures for rs_audio_ramps: headless Chromium's own Web Audio renders each case's AudioParam automation
// (a ConstantSourceNode's offset, default value 1, in an OfflineAudioContext at 48 kHz) and writes the samples.
// Usage: PLAYWRIGHT=/path/to/node_modules/playwright-core node tools/make_fixtures.reference.mjs
import { createRequire } from 'module';
import { writeFileSync } from 'fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT);

const RATE = 48000, LENGTH = 4800;  // 0.1 s
// each event: [method, value, time, timeConstant?]
const cases = {
  default_only: [],
  set_value: [['setValueAtTime', 0.5, 0.01]],
  linear_ramp: [['setValueAtTime', 1, 0], ['linearRampToValueAtTime', 0, 0.05]],
  exponential_decay: [['setValueAtTime', 1, 0.01], ['exponentialRampToValueAtTime', 0.001, 0.06]],
  exponential_from_zero: [['setValueAtTime', 0, 0], ['exponentialRampToValueAtTime', 1, 0.05]],
  exponential_opposite_signs: [['setValueAtTime', -0.5, 0.005], ['exponentialRampToValueAtTime', 0.5, 0.04]],
  ramp_without_earlier_event: [['linearRampToValueAtTime', 0, 0.04]],
  exponential_without_earlier_event: [['exponentialRampToValueAtTime', 0.25, 0.03]],
  set_target: [['setValueAtTime', 1, 0], ['setTargetAtTime', 0.2, 0.02, 0.01]],
  set_target_then_set_value: [['setTargetAtTime', 0.0, 0.01, 0.005], ['setValueAtTime', 0.8, 0.05]],
  same_time_later_wins: [['setValueAtTime', 0.3, 0.02], ['setValueAtTime', 0.7, 0.02]],
  ramp_ends_between_samples: [['setValueAtTime', 1, 0], ['linearRampToValueAtTime', 0, 0.0201234]],
  chained: [['linearRampToValueAtTime', 0.5, 0.02], ['exponentialRampToValueAtTime', 0.05, 0.05], ['linearRampToValueAtTime', 0.8, 0.08]],
  value_after_ramp: [['setValueAtTime', 1, 0], ['linearRampToValueAtTime', 0, 0.05], ['setValueAtTime', 0.6, 0.07001], ['exponentialRampToValueAtTime', 0.1, 0.09]],
  out_of_order_calls: [['linearRampToValueAtTime', 0.2, 0.06], ['setValueAtTime', 0.9, 0.01]],
  target_after_target: [['setTargetAtTime', 0.0, 0.01, 0.01], ['setTargetAtTime', 1.0, 0.04, 0.005]],
  ramp_after_target: [['setTargetAtTime', 0.1, 0.0, 0.01], ['setValueAtTime', 0.4, 0.03], ['exponentialRampToValueAtTime', 0.9, 0.07]],
};

const browser = await chromium.launch();
const page = await browser.newPage();
const out = {};
for (const [name, events] of Object.entries(cases)) {
  out[name] = await page.evaluate(async ({ events, RATE, LENGTH }) => {
    const ctx = new OfflineAudioContext(1, LENGTH, RATE);
    const src = new ConstantSourceNode(ctx);
    for (const [m, v, t, tc] of events) tc === undefined ? src.offset[m](v, t) : src.offset[m](v, t, tc);
    src.connect(ctx.destination);
    src.start(0);
    const buf = await ctx.startRendering();
    return Array.from(buf.getChannelData(0));
  }, { events, RATE, LENGTH });
}
await browser.close();
const dir = new URL('../fixtures/', import.meta.url);
writeFileSync(new URL('cases.txt', dir), Object.entries(cases).map(([n, ev]) =>
  [n, ...ev.map(e => e.join(' '))].join('|')).join('\n') + '\n');
for (const [n, s] of Object.entries(out)) writeFileSync(new URL(`${n}.txt`, dir), s.map(v => v.toPrecision(9)).join('\n') + '\n');
