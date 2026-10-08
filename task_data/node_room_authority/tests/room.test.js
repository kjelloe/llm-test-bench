import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRoom, REJECT, MAX_FRAME_BYTES } from '../src/room.js';

function setup(overrides = {}) {
  let clock = 1000;
  const room = createRoom({
    width: 20,
    height: 12,
    units: [
      { id: 1, team: 0, x: 2, y: 2 },
      { id: 2, team: 0, x: 5, y: 5 },
      { id: 7, team: 1, x: 15, y: 9 },
    ],
    now: () => clock,
    ...overrides,
  });
  room.connect('a', 0);
  room.connect('b', 1);
  room.connect('spec', -1);
  return { room, advance: ms => { clock += ms; } };
}

const send = (room, conn, msg) => room.receive(conn, typeof msg === 'string' ? msg : JSON.stringify(msg));
const move = (seq, unitId, x, y) => ({ type: 'move', seq, unitId, x, y });

test('accepts a valid move and applies it on the next tick, one cell per axis per tick', () => {
  const { room } = setup();
  assert.deepEqual(send(room, 'a', move(1, 1, 5, 3)), { ok: true });
  assert.deepEqual(room.units()[0], { id: 1, team: 0, x: 2, y: 2 }, 'nothing moves before the tick');

  const r1 = room.tick();
  assert.equal(r1.tick, 1);
  assert.deepEqual(r1.applied, [{ team: 0, type: 'move', unitId: 1 }]);
  assert.deepEqual(room.units()[0], { id: 1, team: 0, x: 3, y: 3 });
  room.tick();
  room.tick();
  assert.deepEqual(room.units()[0], { id: 1, team: 0, x: 5, y: 3 });
  room.tick();
  assert.deepEqual(room.units()[0], { id: 1, team: 0, x: 5, y: 3 }, 'stays at the target');
  assert.deepEqual(room.tick().applied, []);
});

test('stop clears the target', () => {
  const { room } = setup();
  send(room, 'a', move(1, 1, 10, 2));
  room.tick();
  assert.deepEqual(send(room, 'a', { type: 'stop', seq: 2, unitId: 1 }), { ok: true });
  assert.deepEqual(room.tick().applied, [{ team: 0, type: 'stop', unitId: 1 }]);
  room.tick();
  assert.equal(room.units()[0].x, 3);
});

test('commands apply in arrival order across teams', () => {
  const { room } = setup();
  send(room, 'b', move(1, 7, 10, 9));
  send(room, 'a', move(1, 2, 6, 6));
  send(room, 'a', { type: 'stop', seq: 2, unitId: 2 });
  assert.deepEqual(room.tick().applied, [
    { team: 1, type: 'move', unitId: 7 },
    { team: 0, type: 'move', unitId: 2 },
    { team: 0, type: 'stop', unitId: 2 },
  ]);
  assert.deepEqual(room.units().map(u => [u.x, u.y]), [[2, 2], [5, 5], [14, 9]]);
});

test('unknown connections are rejected', () => {
  const { room } = setup();
  assert.deepEqual(send(room, 'nobody', move(1, 1, 3, 3)), { ok: false, reason: REJECT.notConnected });
});

test('frames over the size limit are rejected by byte length, Buffers included', () => {
  const { room } = setup();
  const pad = 'x'.repeat(MAX_FRAME_BYTES);
  assert.equal(send(room, 'a', { ...move(1, 1, 3, 3), pad }).reason, REJECT.badFrame);
  // 400 three-byte characters: under 1024 characters but over 1024 bytes.
  const wide = JSON.stringify({ ...move(1, 1, 3, 3), note: '€'.repeat(400) });
  assert.ok(wide.length < MAX_FRAME_BYTES);
  assert.equal(send(room, 'a', wide).reason, REJECT.badFrame);
  assert.deepEqual(room.receive('a', Buffer.from(JSON.stringify(move(1, 1, 3, 3)))), { ok: true });
});

test('malformed JSON and bad shapes are classified', () => {
  const { room } = setup();
  assert.equal(send(room, 'a', '{"type":').reason, REJECT.badJson);
  assert.equal(send(room, 'a', 'null').reason, REJECT.badShape);
  assert.equal(send(room, 'a', '[1,2]').reason, REJECT.badShape);
  assert.equal(send(room, 'a', '"move"').reason, REJECT.badShape);
  assert.equal(send(room, 'a', { seq: 1, unitId: 1 }).reason, REJECT.badShape);
  assert.equal(send(room, 'a', { type: 5 }).reason, REJECT.badShape);
});

test('server-owned and unknown types are rejected, including Object.prototype names', () => {
  const { room } = setup();
  assert.equal(send(room, 'a', { type: 'tick', seq: 1 }).reason, REJECT.serverOwned);
  assert.equal(send(room, 'a', { type: 'teleport', seq: 1, unitId: 1 }).reason, REJECT.unknownType);
  for (const t of ['constructor', 'toString', '__proto__', 'hasOwnProperty', 'valueOf']) {
    assert.equal(send(room, 'a', `{"type":"${t}","seq":1,"unitId":1}`).reason, REJECT.unknownType, t);
  }
});

test('spectators cannot command', () => {
  const { room } = setup();
  assert.equal(send(room, 'spec', move(1, 1, 3, 3)).reason, REJECT.spectator);
  assert.equal(send(room, 'spec', { type: 'tick' }).reason, REJECT.serverOwned, 'serverOwned is checked first');
});

test('field validation: integers, in bounds, seq present', () => {
  const { room } = setup();
  const bad = [
    move(1, 1, 20, 3),
    move(2, 1, 3, 12),
    move(3, 1, -1, 3),
    move(4, 1, 2.5, 3),
    move(5, '1', 3, 3),
    { type: 'move', unitId: 1, x: 3, y: 3 },
    move(-1, 1, 3, 3),
    move(6, 1, '3', 3),
    { type: 'stop', seq: 7 },
  ];
  for (const m of bad) assert.equal(send(room, 'a', m).reason, REJECT.badField, JSON.stringify(m));
  assert.deepEqual(send(room, 'a', move(8, 1, 19, 11)), { ok: true });
});

test('ownership is checked against the connection seat, never the payload', () => {
  const { room } = setup();
  assert.equal(send(room, 'a', move(1, 99, 3, 3)).reason, REJECT.noSuchUnit);
  assert.equal(send(room, 'a', move(2, 7, 3, 3)).reason, REJECT.notYourUnit);
  // Forged identity fields are ignored.
  assert.equal(send(room, 'a', { ...move(3, 7, 3, 3), team: 1, playerId: 'b' }).reason, REJECT.notYourUnit);
  assert.deepEqual(send(room, 'b', { ...move(1, 7, 3, 3), team: 0 }), { ok: true });
  assert.deepEqual(room.tick().applied, [{ team: 1, type: 'move', unitId: 7 }]);
});

test('seq must strictly increase per connection; rejected frames do not advance it', () => {
  const { room } = setup();
  assert.deepEqual(send(room, 'a', move(5, 1, 3, 3)), { ok: true });
  assert.equal(send(room, 'a', move(5, 1, 4, 4)).reason, REJECT.staleSeq, 'duplicate');
  assert.equal(send(room, 'a', move(4, 1, 4, 4)).reason, REJECT.staleSeq, 'older');
  assert.equal(send(room, 'a', move(9, 7, 4, 4)).reason, REJECT.notYourUnit);
  assert.deepEqual(send(room, 'a', move(6, 1, 4, 4)), { ok: true }, 'the rejected seq 9 was not recorded');
  assert.deepEqual(send(room, 'b', move(1, 7, 4, 4)), { ok: true }, 'seq is per connection');
});

test('token bucket per seat: burst, then refill over time', () => {
  const { room, advance } = setup({ cmdBurst: 3, cmdRefillPerSec: 2 });
  for (let i = 1; i <= 3; i++) assert.deepEqual(send(room, 'a', move(i, 1, 3, 3)), { ok: true });
  assert.equal(send(room, 'a', move(4, 1, 3, 3)).reason, REJECT.rateLimited);
  assert.deepEqual(send(room, 'b', move(1, 7, 3, 3)), { ok: true }, 'other seats have their own bucket');
  advance(499);
  assert.equal(send(room, 'a', move(5, 1, 3, 3)).reason, REJECT.rateLimited);
  advance(1); // 500 ms at 2/s = one token
  assert.deepEqual(send(room, 'a', move(6, 1, 3, 3)), { ok: true });
  assert.equal(send(room, 'a', move(7, 1, 3, 3)).reason, REJECT.rateLimited);
  advance(60000);
  for (let i = 8; i <= 10; i++) assert.deepEqual(send(room, 'a', move(i, 1, 3, 3)), { ok: true });
  assert.equal(send(room, 'a', move(11, 1, 3, 3)).reason, REJECT.rateLimited, 'refill is capped at the burst');
});

test('invalid commands still spend tokens; unparseable frames do not', () => {
  const { room } = setup({ cmdBurst: 2, cmdRefillPerSec: 1 });
  assert.equal(send(room, 'a', move(1, 7, 3, 3)).reason, REJECT.notYourUnit);
  assert.equal(send(room, 'a', move(2, 1, 99, 3)).reason, REJECT.badField);
  assert.equal(send(room, 'a', move(3, 1, 3, 3)).reason, REJECT.rateLimited);
  const { room: r2 } = setup({ cmdBurst: 1, cmdRefillPerSec: 1 });
  assert.equal(send(r2, 'a', '{oops').reason, REJECT.badJson);
  assert.equal(send(r2, 'a', { type: 'teleport' }).reason, REJECT.unknownType);
  assert.deepEqual(send(r2, 'a', move(1, 1, 3, 3)), { ok: true });
});

test('a second socket or a reconnect on the same seat shares the bucket', () => {
  const { room } = setup({ cmdBurst: 2, cmdRefillPerSec: 1 });
  room.connect('a2', 0);
  assert.deepEqual(send(room, 'a', move(1, 1, 3, 3)), { ok: true });
  assert.deepEqual(send(room, 'a2', move(1, 2, 6, 6)), { ok: true });
  assert.equal(send(room, 'a2', move(2, 2, 6, 6)).reason, REJECT.rateLimited);
  room.disconnect('a');
  room.connect('a', 0);
  assert.equal(send(room, 'a', move(1, 1, 3, 3)).reason, REJECT.rateLimited);
});

test('disconnect drops queued commands; a reconnect starts a fresh seq', () => {
  const { room } = setup();
  send(room, 'a', move(10, 1, 3, 3));
  room.disconnect('a');
  assert.equal(send(room, 'a', move(11, 1, 3, 3)).reason, REJECT.notConnected);
  room.connect('a', 0);
  assert.deepEqual(send(room, 'a', move(1, 2, 6, 6)), { ok: true }, 'new connection, fresh seq');
  assert.deepEqual(room.tick().applied, [{ team: 0, type: 'move', unitId: 2 }], 'the pre-disconnect command is gone');
});

test('units() returns copies sorted by id', () => {
  const { room } = setup();
  const list = room.units();
  assert.deepEqual(list.map(u => u.id), [1, 2, 7]);
  list[0].x = 999;
  assert.equal(room.units()[0].x, 2);
});
