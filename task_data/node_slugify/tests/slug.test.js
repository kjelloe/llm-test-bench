import { test } from 'node:test';
import assert from 'node:assert/strict';
import { slugify } from '../src/slug.js';

test('basic lowercase and spaces', () => {
  assert.equal(slugify('Hello World'), 'hello-world');
});

test('punctuation is stripped', () => {
  assert.equal(slugify('Hello, World!'), 'hello-world');
});

test('multiple spaces collapse to one hyphen', () => {
  assert.equal(slugify('Hello   World'), 'hello-world');
});

test('leading and trailing spaces are trimmed', () => {
  assert.equal(slugify('  Hello World  '), 'hello-world');
});

test('apostrophes are removed', () => {
  assert.equal(slugify("It's a Test!"), 'its-a-test');
});

test('consecutive hyphens collapse', () => {
  assert.equal(slugify('foo--bar!!baz'), 'foo-bar-baz');
});
