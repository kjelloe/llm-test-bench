import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Game } from '../src/game.js';

let _testIdSeq = 1000;
function testId() { return _testIdSeq++; }

function run(game, ticks, action = 'none') {
  for (let i = 0; i < ticks; i++) {
    game.input(action);
    game.tick();
  }
}

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
