// Regenerates fixtures/*.txt from the game's own JS (js/). usage: node tools/make_fixtures.reference.mjs
// movement.mjs, const.mjs, fixedmath.mjs are verbatim copies of boombrawl/shared (commit 849b401), arena.txt a captured arena.
import { readFileSync, writeFileSync } from 'node:fs';
import { stepEntity } from '../js/movement.mjs';
import { worldToCell } from '../js/fixedmath.mjs';
import { makeRng } from '../js/rng.mjs';
import { CELL, HALF, GRID_W, GRID_H, ASSIST_MIN, SPEED_BASE, SPEED_STEP, SPEED_MAX } from '../js/const.mjs';

const here = (p) => new URL(p, import.meta.url);
const grid = readFileSync(here('../js/arena.txt'), 'utf8').trim();
const blocked = (cx, cy) => cx < 0 || cy < 0 || cx >= GRID_W || cy >= GRID_H || grid[cy * GRID_W + cx] !== '.';
const speeds = [];
for (let s = SPEED_BASE; s <= SPEED_MAX; s += SPEED_STEP) speeds.push(s);
const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const rows = [];
const step = (x, y, dx, dy, sp) => { const r = stepEntity(x, y, dx, dy, sp, blocked); rows.push([x, y, dx, dy, sp, r.x, r.y]); return r; };

// every wall approach at lane offsets around the corner-assist threshold
for (let cy = 1; cy < GRID_H - 1; cy++) for (let cx = 1; cx < GRID_W - 1; cx++) {
  if (blocked(cx, cy)) continue;
  for (const [dx, dy] of DIRS) {
    if (!blocked(cx + dx, cy + dy)) continue;
    for (const sp of [SPEED_BASE, SPEED_MAX]) for (const off of [-70, -ASSIST_MIN, -(ASSIST_MIN - 1), 0, ASSIST_MIN - 1, ASSIST_MIN, 70]) {
      const along = (CELL >> 1) - 10;
      step(cx * CELL + HALF + (dx !== 0 ? dx * along : off), cy * CELL + HALF + (dy !== 0 ? dy * along : off), dx, dy, sp);
    }
  }
}
// seeded walks, both directions at once (x wins), standing still
const rng = makeRng(0x9e3779b9);
const free = [];
for (let cy = 0; cy < GRID_H; cy++) for (let cx = 0; cx < GRID_W; cx++) if (!blocked(cx, cy)) free.push([cx, cy]);
for (let w = 0; w < 30; w++) {
  const [cx, cy] = free[Math.floor(rng.next() * free.length)];
  let x = cx * CELL + HALF, y = cy * CELL + HALF, [dx, dy] = DIRS[w % 4];
  const sp = speeds[w % speeds.length];
  for (let t = 0; t < 100; t++) {
    if (rng.next() < 0.15) [dx, dy] = DIRS[Math.floor(rng.next() * 4)];
    if (rng.next() < 0.05) { dx = 0; dy = 0; }
    ({ x, y } = step(x, y, dx, dy, sp));
  }
}
step(HALF + CELL, HALF + CELL, 1, 1, SPEED_BASE);
step(HALF + CELL * 3, HALF + CELL, -1, -1, SPEED_MAX);
writeFileSync(here('../fixtures/movement.txt'), rows.map(r => r.join(' ')).join('\n') + '\n');

const cells = [0, 1, 255, 256, 257, 6399, 6400, -1, -128, -255, -256, -257, -512, -513, -65536, 2147483392, -2147483648];
writeFileSync(here('../fixtures/world_to_cell.txt'), cells.map(w => `${w} ${worldToCell(w)}`).join('\n') + '\n');

const out = [];
for (const s of [0x9e3779b9, 1, 0xffffffff, 0x80000000, 12345]) {
  const r = makeRng(s);
  for (let i = 0; i < 400; i++) { const u = r.nextU32(); out.push(`${s >>> 0} ${i} ${u} ${u / 4294967296}`); }
}
writeFileSync(here('../fixtures/rng.txt'), out.join('\n') + '\n');
