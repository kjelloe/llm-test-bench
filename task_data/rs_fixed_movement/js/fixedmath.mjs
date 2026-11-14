// shared/fixedmath.mjs — 256-units-per-cell helpers, pure integer math.
import { CELL, HALF } from './const.mjs';

export function cellToWorld(c) {
  return c * CELL + HALF;
}

export function worldToCell(w) {
  return Math.floor(w / CELL);
}

export function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}
