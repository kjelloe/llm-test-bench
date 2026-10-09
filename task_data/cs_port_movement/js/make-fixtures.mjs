// Regenerates tests/GameClientTests/fixtures.json from the real boombrawl movement code.
// usage: node js/make-fixtures.mjs > tests/GameClientTests/fixtures.json
// movement.mjs, const.mjs, fixedmath.mjs are verbatim copies of boombrawl/shared (commit 849b401);
// arena.txt is a real 25x17 arena captured from the running game (unityworks capture.mjs).
import { readFileSync } from 'node:fs';
import { stepEntity } from './movement.mjs';
import { worldToCell } from './fixedmath.mjs';
import { CELL, HALF, GRID_W, GRID_H, ASSIST_MIN, SPEED_BASE, SPEED_STEP, SPEED_MAX } from './const.mjs';

const grid = readFileSync(new URL('./arena.txt', import.meta.url), 'utf8').trim();
const blocked = (cx, cy) => cx < 0 || cy < 0 || cx >= GRID_W || cy >= GRID_H || grid[cy * GRID_W + cx] !== '.';
const speeds = [];
for (let s = SPEED_BASE; s <= SPEED_MAX; s += SPEED_STEP) speeds.push(s);
const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const step = (x, y, dx, dy, sp) => { const r = stepEntity(x, y, dx, dy, sp, blocked); return [x, y, dx, dy, sp, r.x, r.y]; };

// 1. Lane-offset sweep against every wall approach: the corner-assist branch only fires at
//    |offset| >= ASSIST_MIN, which random walks essentially never hit (a real port incident).
const thresholds = [];
for (let cy = 1; cy < GRID_H - 1; cy++) {
  for (let cx = 1; cx < GRID_W - 1; cx++) {
    if (blocked(cx, cy)) continue;
    for (const [dx, dy] of DIRS) {
      if (!blocked(cx + dx, cy + dy)) continue;
      for (const sp of [SPEED_BASE, SPEED_MAX]) {
        for (const off of [-70, -65, -ASSIST_MIN, -(ASSIST_MIN - 1), -30, 0, 30, ASSIST_MIN - 1, ASSIST_MIN, 65, 70]) {
          // Start close to the wall face so the lead point crosses into the blocked cell.
          const along = (CELL >> 1) - 10;
          const x = cx * CELL + HALF + (dx !== 0 ? dx * along : off);
          const y = cy * CELL + HALF + (dy !== 0 ? dy * along : off);
          thresholds.push(step(x, y, dx, dy, sp));
        }
      }
    }
  }
}

// 2. Seeded random walks on the arena at every speed, changing direction now and then.
let seed = 0x9e3779b9 >>> 0;
const rand = () => { seed ^= seed << 13; seed >>>= 0; seed ^= seed >>> 17; seed ^= seed << 5; seed >>>= 0; return seed / 4294967296; };
const free = [];
for (let cy = 0; cy < GRID_H; cy++) for (let cx = 0; cx < GRID_W; cx++) if (!blocked(cx, cy)) free.push([cx, cy]);
const walks = [];
for (let w = 0; w < 40; w++) {
  const [cx, cy] = free[Math.floor(rand() * free.length)];
  let x = cx * CELL + HALF, y = cy * CELL + HALF;
  const sp = speeds[w % speeds.length];
  let [dx, dy] = DIRS[w % 4];
  for (let t = 0; t < 120; t++) {
    if (rand() < 0.15) [dx, dy] = DIRS[Math.floor(rand() * 4)];
    if (rand() < 0.05) { dx = 0; dy = 0; }
    const row = step(x, y, dx, dy, sp);
    walks.push(row);
    x = row[5]; y = row[6];
  }
}

// 3. Both directions given at once: x must win.
const diagonal = [step(HALF + CELL, HALF + CELL, 1, 1, SPEED_BASE), step(HALF + CELL * 3, HALF + CELL, -1, -1, SPEED_MAX)];

const worldToCellCases = [0, 1, 255, 256, 257, -1, -255, -256, -257, -512, -513, 6399].map(w => [w, worldToCell(w)]);

process.stdout.write(JSON.stringify({ grid, width: GRID_W, height: GRID_H, thresholds, walks, diagonal, worldToCell: worldToCellCases }) + '\n');
