// Regenerates tests/GameClientTests/fixtures.json from the real CarrierDominion terrain code.
// usage: node js/make-fixtures.mjs > tests/GameClientTests/fixtures.json
// engine/heightmap.js and shared/*.js are verbatim copies of CarrierDominion (commit 527e5f1);
// islands.json holds the 8 islands of a real captured match (unityworks capture.mjs) plus island 8, a
// copy of island 1 with seed 2147483000 (worldgen draws seeds from [0, 2147483646]): a high-seed case.
// seed + 991 then exceeds int.MaxValue, but that wrap is harmless here because the lattice hash only
// keeps the low 32 bits (checked by mutation 2026-10-09), so it is extra coverage, not a trap.
import { readFileSync } from 'node:fs';
import { islandHeightAt, skirtRadius } from './engine/heightmap.js';

const islands = JSON.parse(readFileSync(new URL('./islands.json', import.meta.url), 'utf8'));
const samples = [];

islands.forEach((isl, i) => {
  const skirt = skirtRadius(isl);
  const reach = Math.floor((skirt + Math.floor(isl.radius * isl.warpPermil / 1000)) * 1.15);
  // Regular grid over island, shore, shelf and open sea.
  const n = 34;
  for (let gy = 0; gy < n; gy++) {
    for (let gx = 0; gx < n; gx++) {
      const wx = isl.x - reach + Math.floor((2 * reach * gx) / (n - 1));
      const wy = isl.y - reach + Math.floor((2 * reach * gy) / (n - 1));
      samples.push([i, wx, wy, islandHeightAt(isl, wx, wy)]);
    }
  }
  // Rings at the radius and skirt edges, where the piecewise falloff switches branches.
  for (const ring of [isl.radius - 1, isl.radius, isl.radius + 1, skirt - 1, skirt, skirt + 1]) {
    for (let k = 0; k < 64; k++) {
      const a = (2 * Math.PI * k) / 64;
      const wx = isl.x + Math.round(ring * Math.cos(a));
      const wy = isl.y + Math.round(ring * Math.sin(a));
      samples.push([i, wx, wy, islandHeightAt(isl, wx, wy)]);
    }
  }
  // The centre, and points left/up of it (negative offsets exercise floor division).
  for (const [ox, oy] of [[0, 0], [-1, -1], [-isl.noiseCell, -isl.noiseCell - 3], [-isl.warpCell - 7, 5]]) {
    samples.push([i, isl.x + ox, isl.y + oy, islandHeightAt(isl, isl.x + ox, isl.y + oy)]);
  }
});

const skirts = islands.map(isl => skirtRadius(isl));
process.stdout.write(JSON.stringify({ islands, skirts, samples }) + '\n');
