// Paratrooper (1982) — headless game backend
// STEP 3 OF 4: Helicopters, paratroopers, and overrun conditions.
//
// Steps 1-2 are already implemented. Implement the four methods marked TODO:
//   _spawnHelicopters()   — spawn one helicopter when tickCount >= _nextHelicopterTick;
//                           advance _nextHelicopterTick; choose side via RNG (<0.5 = left);
//                           random y in [helicopterMinY, helicopterMaxY];
//                           push { id, x, y, direction, speed, state:'active', _nextDropTick }
//   _updateHelicopters()  — move each active helicopter by direction*speed per tick;
//                           drop paratrooper when tickCount >= _nextDropTick (reset interval);
//                           set state='exiting' when off-screen; filter exiting helicopters out
//   _updateParatroopers() — chute state descends at paratrooperDescentRate px/tick;
//                           freefall state descends at paratrooperFreefallRate px/tick;
//                           when y >= groundY and state is chute: set state='landed', record side
//                           (x < turretX → landedLeft++, else landedRight++);
//                           when y >= groundY and state is freefall: kill any landed paratroopers
//                           in same column (|other.x - p.x| <= paratrooperRadius*2), decrement
//                           the appropriate landed counter, then set p.state='dead'
//   _checkLoseConditions()— if landedLeft >= overrunThreshold → over=true, outcome='overrun_left';
//                           if landedRight >= overrunThreshold → over=true, outcome='overrun_right'
//
// Do not modify any other method.

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

function mulberry32(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function dist(ax, ay, bx, by) {
  const dx = ax - bx, dy = ay - by;
  return Math.sqrt(dx * dx + dy * dy);
}

export class Game {
  constructor(config = {}) {
    this.cfg = { ...DEFAULTS, ...config };
    this._rng = mulberry32(this.cfg.seed);
    this._nextId = 1;

    this.tickCount = 0;
    this.score = 0;
    this.landedLeft = 0;
    this.landedRight = 0;
    this.over = false;
    this.outcome = null;

    this.turret = {
      x: this.cfg.turretX,
      y: this.cfg.turretY,
      angleDeg: this.cfg.turretAngle,
      alive: true,
    };

    this.helicopters = [];
    this.jets = [];
    this.paratroopers = [];
    this.bombs = [];
    this.projectiles = [];

    this._pendingInput = 'none';
    this._nextHelicopterTick = this.cfg.helicopterSpawnInterval;
    this._nextJetTick = this.cfg.jetSpawnInterval;
  }

  _id() { return this._nextId++; }
  _rand() { return this._rng(); }

  input(action) { this._pendingInput = action; }

  tick() {
    if (this.over) return;
    this.tickCount++;
    this._processInput();
    this._spawnHelicopters();
    this._spawnJets();
    this._updateHelicopters();
    this._updateJets();
    this._updateParatroopers();
    this._updateBombs();
    this._updateProjectiles();
    this._checkCollisions();
    this._checkLoseConditions();
    this._pendingInput = 'none';
  }

  _processInput() {
    const cfg = this.cfg;
    const t = this.turret;
    if (this._pendingInput === 'rotate_left') {
      t.angleDeg = Math.max(0, t.angleDeg - cfg.turretRotateSpeed);
    } else if (this._pendingInput === 'rotate_right') {
      t.angleDeg = Math.min(180, t.angleDeg + cfg.turretRotateSpeed);
    } else if (this._pendingInput === 'fire') {
      this.score -= cfg.scoreShotCost;
      const rad = (180 - t.angleDeg) * Math.PI / 180;
      const dx = Math.cos(rad) * cfg.projectileSpeed;
      const dy = -Math.sin(rad) * cfg.projectileSpeed;
      this.projectiles.push({ id: this._id(), x: t.x, y: t.y, dx, dy, alive: true });
    }
  }

  _spawnHelicopters() {
    // TODO: implement
  }

  _spawnJets()   {}   // implemented in step 4
  _updateJets()  {}   // implemented in step 4
  _updateBombs() {}   // implemented in step 4

  _updateHelicopters() {
    // TODO: implement
  }

  _updateParatroopers() {
    // TODO: implement
  }

  _updateProjectiles() {
    const cfg = this.cfg;
    for (const p of this.projectiles) {
      if (!p.alive) continue;
      p.x += p.dx;
      p.y += p.dy;
      if (p.x < 0 || p.x > cfg.width || p.y < 0 || p.y > cfg.height) {
        p.alive = false;
      }
    }
    this.projectiles = this.projectiles.filter(p => p.alive);
  }

  _checkCollisions() {}   // implemented in step 4

  _checkLoseConditions() {
    // TODO: implement
  }

  isOver() { return this.over; }

  getResult() {
    return {
      outcome: this.outcome,
      score: this.score,
      landedLeft: this.landedLeft,
      landedRight: this.landedRight,
    };
  }

  getState() {
    return {
      tick: this.tickCount,
      score: this.score,
      turret: { ...this.turret },
      landedLeft: this.landedLeft,
      landedRight: this.landedRight,
      helicopters: this.helicopters.map(h => ({ ...h })),
      jets: this.jets.map(j => ({ ...j })),
      paratroopers: this.paratroopers.map(p => ({ ...p })),
      bombs: this.bombs.map(b => ({ ...b })),
      projectiles: this.projectiles.map(p => ({ ...p })),
      over: this.over,
      outcome: this.outcome,
    };
  }
}
