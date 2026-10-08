// src/seats.js — seat ownership across disconnects for the match server.
// Pure and socket-free: sockets are opaque ids, the clock and token generator are
// injected, and every side effect the transport must perform is returned as an event.

export const GRACE_MS = 90000;

// options: { teams: number[], graceMs = GRACE_MS, now = Date.now, newToken }
export function createSeats(options) {
  const { teams, graceMs = GRACE_MS, now = Date.now, newToken } = options;
  const seats = new Map(); // team -> { state, name, token, socketId, untilMs }
  for (const team of [...teams].sort((a, b) => a - b)) {
    seats.set(team, { state: 'free', name: null, token: null, socketId: null, untilMs: 0 });
  }

  function seatOfSocket(socketId) {
    for (const [team, s] of seats) if (s.state === 'live' && s.socketId === socketId) return team;
    return -1;
  }

  function firstIn(state) {
    for (const [team, s] of seats) if (s.state === state) return team;
    return -1;
  }

  return {
    join(socketId, name) {
      if (seatOfSocket(socketId) !== -1) return { ok: false, reason: 'alreadySeated' };
      const clean = typeof name === 'string' ? name.trim() : '';
      if (clean.length < 1 || clean.length > 16) return { ok: false, reason: 'badName' };

      const events = [];
      let team = firstIn('free');
      if (team === -1) {
        team = firstIn('ai');
        if (team === -1) return { ok: false, reason: 'full' };
        events.push({ type: 'aiRelease', team });
      }
      const token = newToken();
      seats.set(team, { state: 'live', name: clean, token, socketId, untilMs: 0 });
      return { ok: true, team, token, events };
    },

    reclaim(socketId, token) {
      if (typeof token !== 'string' || token === '') return { ok: false, reason: 'unknownToken' };
      let team = -1;
      for (const [t, s] of seats) if (s.state !== 'free' && s.token === token) team = t;
      if (team === -1) return { ok: false, reason: 'unknownToken' };
      const seat = seats.get(team);
      const current = seatOfSocket(socketId);
      if (current !== -1 && current !== team) return { ok: false, reason: 'alreadySeated' };

      const events = [];
      if (seat.state === 'live' && seat.socketId !== socketId) {
        events.push({ type: 'close', socketId: seat.socketId, code: 4000, reason: 'superseded' });
      } else if (seat.state === 'ai') {
        events.push({ type: 'aiRelease', team });
      }
      seat.state = 'live';
      seat.socketId = socketId;
      seat.untilMs = 0;
      return { ok: true, team, name: seat.name, events };
    },

    disconnect(socketId) {
      const team = seatOfSocket(socketId);
      if (team === -1) return { held: false };
      const seat = seats.get(team);
      seat.state = 'held';
      seat.socketId = null;
      seat.untilMs = now() + graceMs;
      return { held: true, team, untilMs: seat.untilMs };
    },

    sweep() {
      const events = [];
      const t = now();
      for (const [team, s] of seats) {
        if (s.state === 'held' && s.untilMs <= t) {
          s.state = 'ai';
          events.push({ type: 'aiTakeover', team });
        }
      }
      return events;
    },

    leave(socketId) {
      const team = seatOfSocket(socketId);
      if (team === -1) return { left: false };
      seats.set(team, { state: 'free', name: null, token: null, socketId: null, untilMs: 0 });
      return { left: true, team };
    },

    seats() {
      return [...seats].map(([team, s]) => ({ team, state: s.state, name: s.name }));
    },
  };
}
