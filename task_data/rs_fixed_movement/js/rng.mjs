// The seeded xorshift32 the game's tools and bots use (verbatim from the fixture generator in boombrawl's tests).
export function makeRng(seed) {
  seed = seed >>> 0;
  return {
    nextU32() { seed ^= seed << 13; seed >>>= 0; seed ^= seed >>> 17; seed ^= seed << 5; seed >>>= 0; return seed; },
    next() { return this.nextU32() / 4294967296; },
  };
}
