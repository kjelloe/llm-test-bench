import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createSeats, GRACE_MS } from '../src/seats.js';

function setup(opts = {}) {
  let clock = 10000;
  let n = 0;
  const seats = createSeats({
    teams: [2, 0, 1],
    now: () => clock,
    newToken: () => `tok${++n}`,
    ...opts,
  });
  return { seats, advance: ms => { clock += ms; } };
}

const state = (seats, team) => seats.seats().find(s => s.team === team);

test('join assigns the lowest free team, issues a token, trims the name', () => {
  const { seats } = setup();
  assert.deepEqual(seats.join('s1', '  Ada '), { ok: true, team: 0, token: 'tok1', events: [] });
  assert.deepEqual(seats.join('s2', 'Bob'), { ok: true, team: 1, token: 'tok2', events: [] });
  assert.deepEqual(state(seats, 0), { team: 0, state: 'live', name: 'Ada' });
  assert.deepEqual(seats.seats().map(s => s.team), [0, 1, 2], 'seats() is in team order');
});

test('join validates names and refuses a socket that already has a seat', () => {
  const { seats } = setup();
  assert.deepEqual(seats.join('s1', '   '), { ok: false, reason: 'badName' });
  assert.deepEqual(seats.join('s1', 'x'.repeat(17)), { ok: false, reason: 'badName' });
  assert.deepEqual(seats.join('s1', 42), { ok: false, reason: 'badName' });
  assert.equal(seats.join('s1', 'x'.repeat(16)).ok, true);
  assert.deepEqual(seats.join('s1', 'Again'), { ok: false, reason: 'alreadySeated' });
});

test('a full room refuses newcomers', () => {
  const { seats } = setup();
  seats.join('a', 'A');
  seats.join('b', 'B');
  seats.join('c', 'C');
  assert.deepEqual(seats.join('d', 'D'), { ok: false, reason: 'full' });
});

test('disconnect holds the seat for the grace window; newcomers cannot take it', () => {
  const { seats, advance } = setup();
  seats.join('a', 'A');
  seats.join('b', 'B');
  seats.join('c', 'C');
  assert.deepEqual(seats.disconnect('b'), { held: true, team: 1, untilMs: 10000 + GRACE_MS });
  assert.equal(state(seats, 1).state, 'held');
  assert.deepEqual(seats.join('d', 'D'), { ok: false, reason: 'full' });
  advance(GRACE_MS - 1);
  assert.deepEqual(seats.sweep(), []);
  assert.deepEqual(seats.join('d', 'D'), { ok: false, reason: 'full' });
  assert.deepEqual(seats.disconnect('nobody'), { held: false });
});

test('reclaim within grace restores the same seat with its name', () => {
  const { seats, advance } = setup();
  const { token } = seats.join('a', 'Ada');
  seats.disconnect('a');
  advance(5000);
  assert.deepEqual(seats.reclaim('a2', token), { ok: true, team: 0, name: 'Ada', events: [] });
  assert.equal(state(seats, 0).state, 'live');
  assert.deepEqual(seats.disconnect('a'), { held: false }, 'the old socket id no longer owns the seat');
});

test('the grace window expires into an AI takeover exactly once', () => {
  const { seats, advance } = setup({ graceMs: 1000 });
  seats.join('a', 'A');
  seats.join('b', 'B');
  seats.disconnect('b');
  seats.disconnect('a');
  advance(1000);
  assert.deepEqual(seats.sweep(), [{ type: 'aiTakeover', team: 0 }, { type: 'aiTakeover', team: 1 }]);
  assert.deepEqual(seats.sweep(), []);
  assert.equal(state(seats, 0).state, 'ai');
});

test('the original player can still reclaim from the AI after grace', () => {
  const { seats, advance } = setup({ graceMs: 1000 });
  const { token } = seats.join('a', 'A');
  seats.disconnect('a');
  advance(5000);
  seats.sweep();
  assert.deepEqual(seats.reclaim('a2', token), {
    ok: true, team: 0, name: 'A', events: [{ type: 'aiRelease', team: 0 }],
  });
  assert.equal(state(seats, 0).state, 'live');
});

test('a newcomer may take an AI seat only after free seats run out, retiring the old token', () => {
  const { seats, advance } = setup({ graceMs: 1000 });
  const { token: oldToken } = seats.join('a', 'A');
  seats.disconnect('a');
  advance(1000);
  seats.sweep();
  assert.equal(seats.join('b', 'B').team, 1, 'free seats come first');
  assert.equal(seats.join('c', 'C').team, 2);
  assert.deepEqual(seats.join('d', 'D'), { ok: true, team: 0, token: 'tok4', events: [{ type: 'aiRelease', team: 0 }] });
  assert.deepEqual(state(seats, 0), { team: 0, state: 'live', name: 'D' });
  assert.deepEqual(seats.reclaim('a2', oldToken), { ok: false, reason: 'unknownToken' });
});

test('newest socket wins: reclaiming a live seat closes the old socket with 4000', () => {
  const { seats } = setup();
  const { token } = seats.join('phone', 'A');
  assert.deepEqual(seats.reclaim('laptop', token), {
    ok: true, team: 0, name: 'A', events: [{ type: 'close', socketId: 'phone', code: 4000, reason: 'superseded' }],
  });
  // The superseded socket's close arrives afterwards; it must not put the live seat on hold.
  assert.deepEqual(seats.disconnect('phone'), { held: false });
  assert.equal(state(seats, 0).state, 'live');
  assert.deepEqual(seats.disconnect('laptop'), { held: true, team: 0, untilMs: 10000 + GRACE_MS });
});

test('reclaim by the socket that already holds that seat is a no-op success', () => {
  const { seats } = setup();
  const { token } = seats.join('a', 'A');
  assert.deepEqual(seats.reclaim('a', token), { ok: true, team: 0, name: 'A', events: [] });
});

test('reclaim rejects unknown, empty or non-string tokens and sockets seated elsewhere', () => {
  const { seats } = setup();
  const { token: t0 } = seats.join('a', 'A');
  seats.join('b', 'B');
  assert.deepEqual(seats.reclaim('x', 'nope'), { ok: false, reason: 'unknownToken' });
  assert.deepEqual(seats.reclaim('x', ''), { ok: false, reason: 'unknownToken' });
  assert.deepEqual(seats.reclaim('x', undefined), { ok: false, reason: 'unknownToken' });
  assert.deepEqual(seats.reclaim('x', { token: t0 }), { ok: false, reason: 'unknownToken' });
  assert.deepEqual(seats.reclaim('b', t0), { ok: false, reason: 'alreadySeated' });
});

test('leave frees the seat immediately and retires its token', () => {
  const { seats } = setup();
  const { token } = seats.join('a', 'A');
  assert.deepEqual(seats.leave('a'), { left: true, team: 0 });
  assert.deepEqual(state(seats, 0), { team: 0, state: 'free', name: null });
  assert.deepEqual(seats.reclaim('a', token), { ok: false, reason: 'unknownToken' });
  assert.equal(seats.join('z', 'Z').team, 0);
  assert.deepEqual(seats.leave('nobody'), { left: false });
});

test('a reclaimed seat that drops again gets a fresh grace window', () => {
  const { seats, advance } = setup({ graceMs: 1000 });
  const { token } = seats.join('a', 'A');
  seats.disconnect('a');
  advance(900);
  seats.reclaim('a2', token);
  advance(500);
  assert.deepEqual(seats.disconnect('a2'), { held: true, team: 0, untilMs: 11400 + 1000 });
  advance(999);
  assert.deepEqual(seats.sweep(), []);
  advance(1);
  assert.deepEqual(seats.sweep(), [{ type: 'aiTakeover', team: 0 }]);
});
