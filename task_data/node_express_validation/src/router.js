import { Router } from 'express';

export const itemsRouter = Router();

const items = [];
let nextId = 1;

itemsRouter.post('/', (req, res) => {
    const { name, price } = req.body ?? {};

    if (!name) {
        return res.status(400).json({ error: 'name is required' });
    }
    if (price === undefined || price === null) {
        return res.status(400).json({ error: 'price is required' });
    }

    // BUG 1: does not check typeof price === 'number' (accepts "free" etc.)
    // BUG 2: does not check price > 0 (accepts negative and zero prices)
    // BUG 3: does not trim name or reject whitespace-only strings
    // BUG 4: returns 200 instead of 201

    const item = { id: nextId++, name, price };
    items.push(item);
    return res.json(item);
});

itemsRouter.get('/', (_req, res) => {
    res.json(items);
});
