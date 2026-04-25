import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseCSV } from '../src/csv.js';

test('simple unquoted row', () => {
  assert.deepEqual(parseCSV('a,b,c'), [['a', 'b', 'c']]);
});

test('multiple rows', () => {
  assert.deepEqual(parseCSV('a,b\nc,d'), [['a', 'b'], ['c', 'd']]);
});

test('empty field', () => {
  assert.deepEqual(parseCSV('a,,c'), [['a', '', 'c']]);
});

test('quoted field containing comma', () => {
  assert.deepEqual(parseCSV('"Smith, John",30'), [['Smith, John', '30']]);
});

test('quoted field with escaped double-quote', () => {
  assert.deepEqual(parseCSV('"say ""hi""",end'), [['say "hi"', 'end']]);
});

test('multiple quoted fields with unquoted field', () => {
  assert.deepEqual(
    parseCSV('"New York","United States",2024'),
    [['New York', 'United States', '2024']],
  );
});
