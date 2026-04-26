export function memoize(fn) {
  const cache = new Map();
  return function (...args) {
    const key = String(args[0]);
    if (cache.has(key)) return cache.get(key);
    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}
