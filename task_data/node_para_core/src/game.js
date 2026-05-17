// Paratrooper (1982) — headless game backend
// STEP 1 OF 4: Core structure — constructor, state methods, tick counter.
//
// Coordinate system: (0,0) top-left, x right, y down, 320×200
// Turret angle: 0=hard left, 90=straight up, 180=hard right
//
// What to implement in this file:
//   constructor(config)  — merge config with DEFAULTS; init RNG; set all state fields
//   input(action)        — queue 'rotate_left' | 'rotate_right' | 'fire' | 'none'
//   tick()               — if over return; increment tickCount; reset _pendingInput='none'
//   isOver()             — return this.over
//   getResult()          — return { outcome, score, landedLeft, landedRight }
//   getState()           — return deep snapshot (shallow-copy arrays with spread/map)
//
// State fields required:
//   tickCount, score, landedLeft, landedRight, over, outcome
//   turret: { x, y, angleDeg, alive }
//   helicopters[], jets[], paratroopers[], bombs[], projectiles[]
//   _pendingInput, _nextHelicopterTick, _nextJetTick, _nextId, _rng
//
// Default config (all overridable via constructor argument):
const DEFAULTS = {
  width: 320, height: 200, seed: 42,
  turretX: 160, turretY: 185, turretAngle: 90,
  turretRotateSpeed: 3, turretRadius: 8,
  projectileSpeed: 8, projectileRadius: 2,
  helicopterSpeed: 1.5, helicopterRadius: 12,
  helicopterSpawnInterval: 120, helicopterDropInterval: 60,
  helicopterMinY: 20, helicopterMaxY: 80,
  jetSpeed: 3.0, jetRadius: 10,
  jetSpawnInterval: 300, jetBombInterval: 90,
  paratrooperDescentRate: 0.5, paratrooperFreefallRate: 3.0,
  paratrooperRadius: 5, chuteRadius: 8, groundY: 190,
  bombFallRate: 2.0, bombRadius: 4,
  overrunThreshold: 4,
  scoreHelicopter: 150, scoreJet: 200,
  scoreParatrooper: 75, scoreBomb: 50, scoreShotCost: 1,
};

// Seeded RNG — call mulberry32(seed) to get a () => float in [0,1) function.
function mulberry32(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class Game {
  constructor(config = {}) {
    // TODO: implement
  }

  input(action) {
    // TODO: implement
  }

  tick() {
    // TODO: implement — for this step, only needs to: guard on over, increment tickCount, reset _pendingInput
  }

  isOver() {
    // TODO: implement
    return false;
  }

  getResult() {
    // TODO: implement
    return { outcome: null, score: 0, landedLeft: 0, landedRight: 0 };
  }

  getState() {
    // TODO: implement — arrays must be shallow copies (not live references)
    return {
      tick: 0, score: 0,
      turret: { x: 160, y: 185, angleDeg: 90, alive: true },
      landedLeft: 0, landedRight: 0,
      helicopters: [], jets: [], paratroopers: [], bombs: [], projectiles: [],
      over: false, outcome: null,
    };
  }
}
