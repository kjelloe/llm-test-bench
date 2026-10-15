// Verbatim copy of boombrawl client/interpolator.js (renamed .mjs so Node loads it as a module).
// client/interpolator.js — snapshot interpolation for everyone who is not
// you (firepower's pattern). Buffers 20 Hz snaps and samples a fixed delay
// behind the newest. The newest snapshot decides what exists — interpolation
// never resurrects entities the server removed.
export function createInterpolator({ delayMs = 100, capacity = 40 } = {}) {
  const buffer = []; // { atMs, snap }

  function lerpList(oldList, newList, t) {
    const oldBy = new Map((oldList ?? []).map(e => [e.id, e]));
    return (newList ?? []).map(e => {
      const prev = oldBy.get(e.id);
      if (!prev) return e;
      return {
        ...e,
        x: prev.x + (e.x - prev.x) * t,
        y: prev.y + (e.y - prev.y) * t
      };
    });
  }

  return {
    push(snap, atMs) {
      if (buffer.length && atMs < buffer.at(-1).atMs) return;
      buffer.push({ atMs, snap });
      while (buffer.length > capacity) buffer.shift();
    },
    latest: () => buffer.at(-1)?.snap ?? null,
    sample(nowMs) {
      if (buffer.length === 0) return null;
      const target = nowMs - delayMs;
      let older = null;
      let newer = null;
      for (const e of buffer) {
        if (e.atMs <= target) older = e;
        else { newer = e; break; }
      }
      if (!newer) return buffer.at(-1).snap;
      if (!older) return newer.snap;
      const span = newer.atMs - older.atMs;
      const t = span > 0 ? Math.min(1, Math.max(0, (target - older.atMs) / span)) : 1;
      return {
        ...newer.snap,
        players: lerpList(older.snap.players, newer.snap.players, t),
        bombs: lerpList(older.snap.bombs, newer.snap.bombs, t)
      };
    }
  };
}
