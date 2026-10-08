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

const COMMAND_TYPES = new Set(['move', 'stop']);
const SERVER_OWNED = new Set(['tick']);

// options: { width, height, units: [{ id, team, x, y }], now = Date.now,
//            cmdBurst = 10, cmdRefillPerSec = 5 }
export function createRoom(options) {
  const { width, height, now = Date.now, cmdBurst = 10, cmdRefillPerSec = 5 } = options;
  const units = new Map();
  for (const u of options.units) units.set(u.id, { id: u.id, team: u.team, x: u.x, y: u.y, target: null });

  const conns = new Map(); // connId -> { team, lastSeq, generation }
  const buckets = new Map(); // team -> { tokens, atMs }
  let queue = []; // { connId, generation, team, cmd }
  let tick = 0;
  let generation = 0;

  const reject = reason => ({ ok: false, reason });
  const isInt = v => Number.isInteger(v);

  function takeToken(team) {
    const t = now();
    let b = buckets.get(team);
    if (!b) {
      b = { tokens: cmdBurst, atMs: t };
      buckets.set(team, b);
    }
    b.tokens = Math.min(cmdBurst, b.tokens + ((t - b.atMs) * cmdRefillPerSec) / 1000);
    b.atMs = t;
    if (b.tokens < 1) return false;
    b.tokens -= 1;
    return true;
  }

  function fieldsValid(msg) {
    if (!isInt(msg.seq) || msg.seq < 0) return false;
    if (!isInt(msg.unitId)) return false;
    if (msg.type === 'move') {
      if (!isInt(msg.x) || msg.x < 0 || msg.x >= width) return false;
      if (!isInt(msg.y) || msg.y < 0 || msg.y >= height) return false;
    }
    return true;
  }

  return {
    connect(connId, team) {
      conns.set(connId, { team, lastSeq: -1, generation: ++generation });
    },

    disconnect(connId) {
      conns.delete(connId);
    },

    receive(connId, raw) {
      const conn = conns.get(connId);
      if (!conn) return reject(REJECT.notConnected);
      const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : raw;
      if (typeof text !== 'string' || Buffer.byteLength(text, 'utf8') > MAX_FRAME_BYTES) return reject(REJECT.badFrame);

      let msg;
      try {
        msg = JSON.parse(text);
      } catch {
        return reject(REJECT.badJson);
      }
      if (msg === null || typeof msg !== 'object' || Array.isArray(msg) || typeof msg.type !== 'string') {
        return reject(REJECT.badShape);
      }
      if (SERVER_OWNED.has(msg.type)) return reject(REJECT.serverOwned);
      if (!COMMAND_TYPES.has(msg.type)) return reject(REJECT.unknownType);
      if (conn.team < 0) return reject(REJECT.spectator);
      if (!takeToken(conn.team)) return reject(REJECT.rateLimited);
      if (!fieldsValid(msg)) return reject(REJECT.badField);
      if (msg.seq <= conn.lastSeq) return reject(REJECT.staleSeq);
      const unit = units.get(msg.unitId);
      if (!unit) return reject(REJECT.noSuchUnit);
      if (unit.team !== conn.team) return reject(REJECT.notYourUnit);

      conn.lastSeq = msg.seq;
      const cmd = msg.type === 'move'
        ? { type: 'move', unitId: msg.unitId, x: msg.x, y: msg.y }
        : { type: 'stop', unitId: msg.unitId };
      queue.push({ connId, generation: conn.generation, team: conn.team, cmd });
      return { ok: true };
    },

    tick() {
      tick += 1;
      const applied = [];
      for (const q of queue) {
        const conn = conns.get(q.connId);
        if (!conn || conn.generation !== q.generation) continue;
        const unit = units.get(q.cmd.unitId);
        unit.target = q.cmd.type === 'move' ? { x: q.cmd.x, y: q.cmd.y } : null;
        applied.push({ team: q.team, type: q.cmd.type, unitId: q.cmd.unitId });
      }
      queue = [];
      for (const id of [...units.keys()].sort((a, b) => a - b)) {
        const u = units.get(id);
        if (!u.target) continue;
        u.x += Math.sign(u.target.x - u.x);
        u.y += Math.sign(u.target.y - u.y);
        if (u.x === u.target.x && u.y === u.target.y) u.target = null;
      }
      return { tick, applied };
    },

    units() {
      return [...units.values()]
        .sort((a, b) => a.id - b.id)
        .map(u => ({ id: u.id, team: u.team, x: u.x, y: u.y }));
    },
  };
}
