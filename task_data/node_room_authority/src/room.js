// src/room.js — the authoritative match room. Every client message arrives here
// as a raw WebSocket text frame from an untrusted connection; nothing but this
// module stands between a modified client and another team's units.

export const REJECT = Object.freeze({
  notConnected: 'notConnected',
  badFrame: 'badFrame',
  badJson: 'badJson',
  badShape: 'badShape',
  serverOwned: 'serverOwned',
  unknownType: 'unknownType',
  spectator: 'spectator',
  rateLimited: 'rateLimited',
  badField: 'badField',
  staleSeq: 'staleSeq',
  noSuchUnit: 'noSuchUnit',
  notYourUnit: 'notYourUnit',
});

export const MAX_FRAME_BYTES = 1024;

// options: { width, height, units: [{ id, team, x, y }], now = Date.now,
//            cmdBurst = 10, cmdRefillPerSec = 5 }
export function createRoom(options) {
  throw new Error('not implemented');
}
