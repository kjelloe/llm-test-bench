// Paratrooper (1982) — headless game backend
// STEP 2 OF 4: Turret rotation, firing, and projectile physics.
//
// The constructor, tick(), isOver(), getResult(), getState() are already implemented.
// Implement the two methods marked TODO:
//   _processInput()     — handle rotate_left, rotate_right, fire (angle clamp 0..180,
//                         firing costs scoreShotCost and creates a projectile with dx/dy
//                         from angle: rad=(180-angleDeg)*PI/180, dx=cos(rad)*speed, dy=-sin(rad)*speed)
//   _updateProjectiles() — move each live projectile by dx/dy; mark alive=false if out of
//                          bounds (x<0 || x>width || y<0 || y>height); filter dead ones out
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
    // TODO: implement
    // rotate_left  → decrease angleDeg by turretRotateSpeed, clamp to 0
    // rotate_right → increase angleDeg by turretRotateSpeed, clamp to 180
    // fire         → deduct scoreShotCost; compute dx/dy from angle; push projectile
    //   rad = (180 - angleDeg) * Math.PI / 180
    //   dx = Math.cos(rad) * projectileSpeed
    //   dy = -Math.sin(rad) * projectileSpeed
    //   projectile: { id: this._id(), x: turret.x, y: turret.y, dx, dy, alive: true }
  }

  _spawnHelicopters()  {}   // implemented in step 3
  _spawnJets()         {}   // implemented in step 3
  _updateHelicopters() {}   // implemented in step 3
  _updateJets()        {}   // implemented in step 4
  _updateParatroopers(){}   // implemented in step 3
  _updateBombs()       {}   // implemented in step 4

  _updateProjectiles() {
    // TODO: implement
    // For each live projectile: p.x += p.dx; p.y += p.dy
    // If out of bounds (x<0 || x>width || y<0 || y>height) → p.alive = false
    // Remove dead projectiles: this.projectiles = this.projectiles.filter(p => p.alive)
  }

  _checkCollisions()   {}   // implemented in step 4
  _checkLoseConditions(){}  // implemented in step 3

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
