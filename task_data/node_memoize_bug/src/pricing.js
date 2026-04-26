import { memoize } from './memoize.js';

function _applyDiscount(price, discountPct) {
  return price - price * discountPct / 100;
}

function _computeTax(amount, taxRatePct) {
  return amount * taxRatePct / 100;
}

export const applyDiscount = memoize(_applyDiscount);
export const computeTax = memoize(_computeTax);
