// js/statehash.js — the Node server's canonical state hash. The server publishes
// hashState(state) with every snapshot; a client whose own hash differs has desynced.
// This file is the specification: every client must produce identical bytes.

export function floorDiv(a, b) {
  return Math.floor(a / b) | 0;
}

export function truncDiv(a, b) {
  return Math.trunc(a / b) | 0;
}

// Cell index for a decision keyed to a continuous x position (256 units per cell).
// On an exact cell boundary in the east half of the map, round down so that a
// mirrored map samples mirrored cells.
export function sampleCellX(world, mapWidth) {
  const c = world >> 8;
  return (world & 255) === 0 && 2 * world > mapWidth * 256 ? c - 1 : c;
}

function checkInt(v, min, max, label) {
  if (!Number.isInteger(v) || v < min || v > max) throw new RangeError(`${label} out of range: ${v}`);
}

export function createByteWriter() {
  const bytes = [];
  const w = {
    u8(v) { checkInt(v, 0, 0xff, 'u8'); bytes.push(v); return w; },
    u16(v) { checkInt(v, 0, 0xffff, 'u16'); bytes.push(v & 0xff, (v >>> 8) & 0xff); return w; },
    u32(v) {
      checkInt(v, 0, 0xffffffff, 'u32');
      bytes.push(v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff);
      return w;
    },
    i32(v) {
      checkInt(v, -0x80000000, 0x7fffffff, 'i32');
      const u = v >>> 0;
      bytes.push(u & 0xff, (u >>> 8) & 0xff, (u >>> 16) & 0xff, (u >>> 24) & 0xff);
      return w;
    },
    bool(v) { bytes.push(v ? 1 : 0); return w; },
    optU32(v) { // null/undefined -> 0; otherwise 1 then u32
      if (v === null || v === undefined) bytes.push(0);
      else { bytes.push(1); w.u32(v); }
      return w;
    },
    // u16 byte length, then UTF-8 of each UTF-16 code point; an unpaired surrogate
    // is encoded as its own 3-byte sequence (no replacement character).
    str(s) {
      const out = [];
      for (let i = 0; i < s.length; i++) {
        const code = s.codePointAt(i);
        if (code > 0xffff) i++;
        if (code <= 0x7f) out.push(code);
        else if (code <= 0x7ff) out.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
        else if (code <= 0xffff) out.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
        else out.push(0xf0 | (code >> 18), 0x80 | ((code >> 12) & 0x3f), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
      }
      w.u16(out.length);
      bytes.push(...out);
      return w;
    },
    toBytes() { return Uint8Array.from(bytes); },
  };
  return w;
}

// FNV-1a 64: offset basis 0xcbf29ce484222325, prime 0x100000001b3, low 64 bits.
export function fnv1a64(bytes) {
  let h = 0xcbf29ce484222325n;
  for (const b of bytes) {
    h ^= BigInt(b);
    h = (h * 0x100000001b3n) & 0xffffffffffffffffn;
  }
  return h.toString(16).padStart(16, '0');
}

// Canonical layout: u32 tick, u16 unit count, then units in ascending id order:
// u32 id, u8 team, i32 x, i32 y, u8 heading, u16 hp, bool alive, optU32 target, str name.
export function stateBytes(state) {
  const w = createByteWriter();
  const units = [...state.units].sort((a, b) => a.id - b.id);
  w.u32(state.tick).u16(units.length);
  for (const u of units) {
    w.u32(u.id).u8(u.team).i32(u.x).i32(u.y).u8(u.heading).u16(u.hp).bool(u.alive).optU32(u.target).str(u.name);
  }
  return w.toBytes();
}

export function hashState(state) {
  return fnv1a64(stateBytes(state));
}
