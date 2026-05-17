import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Game } from '../src/game.js';

let _testIdSeq = 1000;
function testId() { return _testIdSeq++; }

// Helper: run N ticks with optional repeated action
function run(game, ticks, action = 'none') {
  for (let i = 0; i < ticks; i++) {
    game.input(action);
    game.tick();
  }
}

// Helper: inject a helicopter directly for deterministic tests
function addHelicopter(game, x, y, direction = 1) {
  const h = { id: testId(), x, y, direction, speed: game.cfg.helicopterSpeed,
               state: 'active', _nextDropTick: Infinity };
  game.helicopters.push(h);
  return h;
}

function addParatrooper(game, x, y, state = 'chute') {
  const p = { id: testId(), x, y, state };
  game.paratroopers.push(p);
  return p;
}

function addBomb(game, x, y) {
  const b = { id: testId(), x, y, state: 'falling', alive: true };
  game.bombs.push(b);
  return b;
}

// ── Initial state ─────────────────────────────────────────────────────────────

test('initial score is 0', () => {
  const g = new Game();
  assert.equal(g.score, 0);
});

test('initial turret angle is 90 (straight up)', () => {
  const g = new Game();
  assert.equal(g.turret.angleDeg, 90);
});

test('turret is at center-bottom', () => {
  const g = new Game();
  assert.equal(g.turret.x, 160);
  assert.ok(g.turret.y > 150);
});

test('game starts not over', () => {
  const g = new Game();
  assert.equal(g.isOver(), false);
  assert.equal(g.getResult().outcome, null);
});

test('landedLeft and landedRight start at 0', () => {
  const g = new Game();
  assert.equal(g.landedLeft, 0);
  assert.equal(g.landedRight, 0);
});

// ── Turret rotation ───────────────────────────────────────────────────────────

test('rotate_left decreases angle', () => {
  const g = new Game();
  g.input('rotate_left');
  g.tick();
  assert.ok(g.turret.angleDeg < 90);
});

test('rotate_right increases angle', () => {
  const g = new Game();
  g.input('rotate_right');
  g.tick();
  assert.ok(g.turret.angleDeg > 90);
});

test('angle clamps at 0', () => {
  const g = new Game();
  run(g, 100, 'rotate_left');
  assert.equal(g.turret.angleDeg, 0);
});

test('angle clamps at 180', () => {
  const g = new Game();
  run(g, 100, 'rotate_right');
  assert.equal(g.turret.angleDeg, 180);
});

// ── Firing and score cost ─────────────────────────────────────────────────────

test('firing costs 1 point', () => {
  const g = new Game();
  g.input('fire');
  g.tick();
  assert.equal(g.score, -1);
});

test('firing twice costs 2 points', () => {
  const g = new Game();
  g.input('fire'); g.tick();
  g.input('fire'); g.tick();
  assert.equal(g.score, -2);
});

test('fire creates a projectile', () => {
  const g = new Game();
  g.input('fire');
  g.tick();
  const state = g.getState();
  assert.equal(state.projectiles.length, 1);
});

test('projectile at 90° travels upward (dy < 0)', () => {
  const g = new Game({ turretAngle: 90 });
  g.input('fire');
  g.tick();
  const p = g.getState().projectiles[0];
  assert.ok(p.dy < 0, `expected dy<0 but got ${p.dy}`);
  assert.ok(Math.abs(p.dx) < 0.01, `expected dx≈0 but got ${p.dx}`);
});

test('projectile at 0° travels left (dx < 0)', () => {
  const g = new Game({ turretAngle: 0 });
  g.input('fire');
  g.tick();
  const p = g.getState().projectiles[0];
  assert.ok(p.dx < 0, `expected dx<0 but got ${p.dx}`);
  assert.ok(Math.abs(p.dy) < 0.01, `expected dy≈0 but got ${p.dy}`);
});

test('projectile at 180° travels right (dx > 0)', () => {
  const g = new Game({ turretAngle: 180 });
  g.input('fire');
  g.tick();
  const p = g.getState().projectiles[0];
  assert.ok(p.dx > 0, `expected dx>0 but got ${p.dx}`);
  assert.ok(Math.abs(p.dy) < 0.01, `expected dy≈0 but got ${p.dy}`);
});

test('projectile moves each tick', () => {
  const g = new Game({ turretAngle: 90 });
  g.input('fire'); g.tick();
  const y0 = g.getState().projectiles[0].y;
  g.tick();
  const y1 = g.getState().projectiles[0].y;
  assert.ok(y1 < y0, 'projectile should move upward each tick');
});

test('projectile disappears off the top of the screen', () => {
  const g = new Game({ turretAngle: 90, turretY: 10, projectileSpeed: 20 });
  g.input('fire'); g.tick();
  run(g, 20);
  assert.equal(g.getState().projectiles.length, 0);
});

// ── Helicopter spawning and movement ─────────────────────────────────────────

test('helicopter spawns after spawn interval', () => {
  const g = new Game({ helicopterSpawnInterval: 5 });
  run(g, 5);
  assert.ok(g.helicopters.length > 0);
});

test('helicopter moves horizontally each tick', () => {
  const g = new Game({ helicopterSpawnInterval: 999 });
  addHelicopter(g, 50, 40, 1);
  const x0 = g.helicopters[0].x;
  g.tick();
  assert.ok(g.helicopters[0].x > x0);
});

test('helicopter moving left-to-right exits and is removed', () => {
  const g = new Game({ helicopterSpawnInterval: 999, helicopterSpeed: 10 });
  addHelicopter(g, 300, 40, 1);
  run(g, 30);
  assert.equal(g.helicopters.length, 0);
});

test('helicopter drops paratrooper at drop interval', () => {
  const g = new Game({ helicopterSpawnInterval: 999 });
  const h = addHelicopter(g, 100, 40, 1);
  h._nextDropTick = 2;
  run(g, 2);
  assert.ok(g.paratroopers.length > 0);
});

// ── Paratrooper descent and landing ──────────────────────────────────────────

test('paratrooper descends each tick while in chute state', () => {
  const g = new Game({ helicopterSpawnInterval: 999 });
  const p = addParatrooper(g, 100, 50, 'chute');
  const y0 = p.y;
  g.tick();
  assert.ok(p.y > y0);
});

test('paratrooper landing left of turret increments landedLeft', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  addParatrooper(g, 80, 180, 'chute');
  g.tick();
  assert.equal(g.landedLeft, 1);
  assert.equal(g.landedRight, 0);
});

test('paratrooper landing right of turret increments landedRight', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  addParatrooper(g, 240, 180, 'chute');
  g.tick();
  assert.equal(g.landedRight, 1);
  assert.equal(g.landedLeft, 0);
});

test('landed paratrooper state is landed', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  const p = addParatrooper(g, 80, 180, 'chute');
  g.tick();
  assert.equal(p.state, 'landed');
});

// ── Overrun (4 on one side) ───────────────────────────────────────────────────

test('4 paratroopers landing left ends game with overrun_left', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  for (let i = 0; i < 4; i++) addParatrooper(g, 80 + i * 5, 180, 'chute');
  g.tick();
  assert.equal(g.isOver(), true);
  assert.equal(g.getResult().outcome, 'overrun_left');
});

test('4 paratroopers landing right ends game with overrun_right', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  for (let i = 0; i < 4; i++) addParatrooper(g, 200 + i * 5, 180, 'chute');
  g.tick();
  assert.equal(g.isOver(), true);
  assert.equal(g.getResult().outcome, 'overrun_right');
});

test('3 left + 3 right does not end game', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  for (let i = 0; i < 3; i++) addParatrooper(g, 80 + i * 5, 180, 'chute');
  for (let i = 0; i < 3; i++) addParatrooper(g, 200 + i * 5, 180, 'chute');
  g.tick();
  assert.equal(g.isOver(), false);
});

test('game does not continue ticking once over', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200 });
  for (let i = 0; i < 4; i++) addParatrooper(g, 80 + i * 5, 180, 'chute');
  g.tick();
  const tick1 = g.tickCount;
  g.tick();
  assert.equal(g.tickCount, tick1);
});

// ── Shooting paratroopers ─────────────────────────────────────────────────────

test('shooting paratrooper body kills it and awards points', () => {
  const g = new Game({ helicopterSpawnInterval: 999 });
  // Use freefall state so there is no chute to intercept the shot
  const p = addParatrooper(g, 160, 100, 'freefall');
  g.input('fire'); g.tick();
  run(g, 20);
  assert.equal(p.state, 'dead');
  assert.ok(g.score > -100, 'score should reflect kill');
});

test('shooting parachute converts to freefall', () => {
  const g = new Game({ helicopterSpawnInterval: 999, chuteRadius: 20 });
  const p = addParatrooper(g, 160, 80, 'chute');
  g.input('fire'); g.tick();
  run(g, 15);
  // Either freefall or dead — chute should have been hit
  assert.ok(p.state === 'freefall' || p.state === 'dead');
});

test('freefall paratrooper descends faster than chute', () => {
  const g = new Game({ helicopterSpawnInterval: 999 });
  const p1 = addParatrooper(g, 80, 50, 'chute');
  const p2 = addParatrooper(g, 200, 50, 'freefall');
  const y1 = p1.y, y2 = p2.y;
  g.tick();
  assert.ok(p2.y - y2 > p1.y - y1, 'freefall should be faster than chute descent');
});

test('freefall paratrooper landing kills landed paratroopers below', () => {
  const g = new Game({ helicopterSpawnInterval: 999, paratrooperDescentRate: 200,
                       paratrooperFreefallRate: 200 });
  // Land one paratrooper first
  const landed = addParatrooper(g, 80, 180, 'chute');
  g.tick();
  assert.equal(landed.state, 'landed');
  assert.equal(g.landedLeft, 1);

  // Now drop a freefalling one on top
  addParatrooper(g, 80, 180, 'freefall');
  g.tick();
  assert.equal(landed.state, 'dead');
  assert.equal(g.landedLeft, 0);
});

// ── Bombs ─────────────────────────────────────────────────────────────────────

test('bomb falls downward each tick', () => {
  const g = new Game({ helicopterSpawnInterval: 999, jetSpawnInterval: 999 });
  const b = addBomb(g, 160, 50);
  const y0 = b.y;
  g.tick();
  assert.ok(b.y > y0);
});

test('bomb hitting turret ends game with bomb_hit', () => {
  const g = new Game({ helicopterSpawnInterval: 999, jetSpawnInterval: 999,
                       bombFallRate: 3 });
  addBomb(g, 160, 160);
  run(g, 15);  // (185-160)/3 ≈ 8 ticks; 15 gives headroom
  assert.equal(g.isOver(), true);
  assert.equal(g.getResult().outcome, 'bomb_hit');
});

test('shooting bomb destroys it and awards points', () => {
  const g = new Game({ helicopterSpawnInterval: 999, jetSpawnInterval: 999,
                       turretAngle: 90 });
  // Place bomb just above turret
  const b = addBomb(g, 160, 120);
  g.input('fire'); g.tick();
  run(g, 15);
  assert.equal(b.state, 'destroyed');
  assert.ok(g.score > -20);
});

// ── Score integrity ───────────────────────────────────────────────────────────

test('killing helicopter awards scoreHelicopter points', () => {
  const g = new Game({ helicopterSpawnInterval: 999, turretAngle: 90,
                       projectileSpeed: 20 });
  // Place helicopter directly above turret
  addHelicopter(g, 160, 80, 1);
  g.input('fire'); g.tick();
  run(g, 10);
  assert.ok(g.score >= g.cfg.scoreHelicopter - g.cfg.scoreShotCost);
});

test('getResult reflects current score', () => {
  const g = new Game();
  g.input('fire'); g.tick();
  assert.equal(g.getResult().score, g.score);
});

// ── getState snapshot ─────────────────────────────────────────────────────────

test('getState returns tick count', () => {
  const g = new Game();
  run(g, 5);
  assert.equal(g.getState().tick, 5);
});

test('getState snapshot is a copy (mutation does not affect game)', () => {
  const g = new Game();
  const s = g.getState();
  s.score = 99999;
  assert.notEqual(g.score, 99999);
});
