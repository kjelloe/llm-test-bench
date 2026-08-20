import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import app from '../src/app.js';

test('POST /items with valid data returns 201', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: 'Widget', price: 9.99 })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 201);
    assert.equal(res.body.name, 'Widget');
    assert.equal(res.body.price, 9.99);
    assert.ok(typeof res.body.id === 'number', 'id should be a number');
});

test('POST /items missing name returns 400', async () => {
    const res = await request(app)
        .post('/items')
        .send({ price: 9.99 })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 400);
    assert.ok(res.body.error, 'should include error field');
});

test('POST /items missing price returns 400', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: 'Widget' })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
});

test('POST /items with non-numeric price returns 400', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: 'Widget', price: 'free' })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
});

test('POST /items with negative price returns 400', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: 'Widget', price: -5 })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
});

test('POST /items with zero price returns 400', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: 'Widget', price: 0 })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
});

test('POST /items with whitespace-only name returns 400', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: '   ', price: 9.99 })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 400);
    assert.ok(res.body.error);
});

test('POST /items name is trimmed in stored item', async () => {
    const res = await request(app)
        .post('/items')
        .send({ name: '  Gadget  ', price: 5.00 })
        .set('Content-Type', 'application/json');
    assert.equal(res.status, 201);
    assert.equal(res.body.name, 'Gadget');
});
