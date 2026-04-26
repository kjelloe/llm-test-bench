import { test } from 'node:test';
import assert from 'node:assert/strict';
import { applyDiscount, computeTax } from '../src/pricing.js';

test('10% off 100 → 90', () => {
  assert.strictEqual(applyDiscount(100, 10), 90);
});

test('10% off 200 → 180', () => {
  assert.strictEqual(applyDiscount(200, 10), 180);
});

test('20% off 100 → 80', () => {
  assert.strictEqual(applyDiscount(100, 20), 80);
});

test('50% off 200 → 100', () => {
  assert.strictEqual(applyDiscount(200, 50), 100);
});

test('0% off 150 → 150', () => {
  assert.strictEqual(applyDiscount(150, 0), 150);
});

test('5% tax on 400 → 20', () => {
  assert.strictEqual(computeTax(400, 5), 20);
});

test('10% tax on 400 → 40', () => {
  assert.strictEqual(computeTax(400, 10), 40);
});

test('15% tax on 600 → 90', () => {
  assert.strictEqual(computeTax(600, 15), 90);
});
