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
