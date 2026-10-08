// src/seats.js — seat ownership across disconnects for the match server.
// Pure and socket-free: sockets are opaque ids, the clock and token generator are
// injected, and every side effect the transport must perform is returned as an event.

export const GRACE_MS = 90000;

// options: { teams: number[], graceMs = GRACE_MS, now = Date.now, newToken }
export function createSeats(options) {
  throw new Error('not implemented');
}
