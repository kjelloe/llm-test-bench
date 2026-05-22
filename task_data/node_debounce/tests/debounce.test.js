import { test } from 'node:test';
import assert from 'node:assert/strict';
import { debounce } from '../src/debounce.js';

const DELAY = 60;                         // ms — debounce window used in all tests
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

test('debounces multiple rapid calls into one', async () => {
  let calls = 0;
  const d = debounce(() => calls++, DELAY);
  d(); d(); d();
  await wait(DELAY * 2);
  assert.equal(calls, 1, `expected 1 call, got ${calls}`);
});

test('does not fire before the delay elapses', async () => {
  let calls = 0;
  const d = debounce(() => calls++, DELAY);
  d();
  await wait(DELAY / 3);
  assert.equal(calls, 0, `should not have fired yet, got ${calls}`);
});

test('passes the final arguments to the callback', async () => {
  let last;
  const d = debounce((x) => { last = x; }, DELAY);
  d(1); d(2); d(3);
  await wait(DELAY * 2);
  assert.equal(last, 3, `expected last arg 3, got ${last}`);
});

test('can fire again after a quiet period', async () => {
  let calls = 0;
  const d = debounce(() => calls++, DELAY);
  d();
  await wait(DELAY * 2);
  assert.equal(calls, 1, `expected 1 call after first burst`);
  d();
  await wait(DELAY * 2);
  assert.equal(calls, 2, `expected 2 calls after second burst`);
});

test('resets the timer when called again within the delay', async () => {
  let calls = 0;
  const d = debounce(() => calls++, DELAY);
  d();                         // first call — timer scheduled
  await wait(DELAY / 3);       // well before DELAY — no fire yet
  d();                         // second call — should reset the timer
  await wait(DELAY / 3);       // still before DELAY from second call
  assert.equal(calls, 0, `expected 0 calls (timer should have been reset)`);
  await wait(DELAY * 2);       // now past DELAY — exactly one firing expected
  assert.equal(calls, 1, `expected 1 call after delay, got ${calls}`);
});
