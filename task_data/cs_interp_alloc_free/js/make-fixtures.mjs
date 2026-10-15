// Prints tests/GameClientTests/fixtures.json from the real interpolator:
//   node js/make-fixtures.mjs > tests/GameClientTests/fixtures.json
// A seeded stream of pushes and samples: players join and leave, bombs appear and burn out, some pushes
// arrive out of order, and the buffer (capacity 8) wraps many times.
import { createInterpolator } from './interpolator.mjs';

let seed = 20261016;
const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
const ri = (a, b) => a + Math.floor(rnd() * (b - a + 1));

const interp = createInterpolator({ delayMs: 100, capacity: 8 });
const ops = [];
const players = new Map();
const bombs = new Map();
let nextBomb = 100;
let t = 1000;
let tick = 0;

function snapNow() {
  return {
    tick,
    players: [...players.values()].map(p => ({ ...p })),
    bombs: [...bombs.values()].map(b => ({ ...b }))
  };
}
const rec = s => s && {
  players: s.players.map(e => ({ id: e.id, x: e.x, y: e.y, kind: e.kind })),
  bombs: s.bombs.map(e => ({ id: e.id, x: e.x, y: e.y, kind: e.kind }))
};

ops.push({ op: 'sample', nowMs: 900, expect: rec(interp.sample(900)) });
for (let i = 0; i < 160; i++) {
  tick++;
  if (players.size < 6 && rnd() < 0.15) { const id = ri(1, 9); if (!players.has(id)) players.set(id, { id, x: ri(1, 20) * 256 + 128, y: ri(1, 14) * 256 + 128, kind: 0 }); }
  if (players.size > 1 && rnd() < 0.05) players.delete([...players.keys()][ri(0, players.size - 1)]);
  for (const p of players.values()) {
    if (rnd() < 0.7) { const s = ri(-60, 60); if (rnd() < 0.5) p.x += s; else p.y += s; }
    if (rnd() < 0.08) p.kind = ri(0, 3);   // a power-up changes what is drawn; the newer snapshot decides
  }
  if (rnd() < 0.2) { const id = nextBomb++; bombs.set(id, { id, x: ri(1, 20) * 256 + 128, y: ri(1, 14) * 256 + 128, kind: ri(1, 3) }); }
  for (const b of bombs.values()) if (rnd() < 0.08) bombs.delete(b.id);
  t += 50 + ri(-12, 12);
  const at = rnd() < 0.05 ? t - ri(60, 140) : t;   // a late packet, older than the newest
  const snap = snapNow();
  interp.push(snap, at);
  ops.push({ op: 'push', atMs: at, snap: rec(snap) });
  if (i % 7 === 3) {
    // Same-time duplicate push (span 0 between two buffered snaps).
    interp.push(snapNow(), at);
    ops.push({ op: 'push', atMs: at, snap: rec(snapNow()) });
  }
  const samples = ri(1, 4);
  for (let k = 0; k < samples; k++) {
    const now = t + ri(-30, 160);
    ops.push({ op: 'sample', nowMs: now, expect: rec(interp.sample(now)) });
  }
}
ops.push({ op: 'sample', nowMs: t + 5000, expect: rec(interp.sample(t + 5000)) });
process.stdout.write(JSON.stringify({ delayMs: 100, capacity: 8, ops }) + '\n');
