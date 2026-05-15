// Paratrooper (1982) — headless game backend
// Coordinate system: (0,0) top-left, x right, y down, 320×200
// Turret angle: 0 = hard left, 90 = straight up, 180 = hard right
// Tick rate: px/tick, no wall-clock

const DEFAULTS = {
  width: 320,
  height: 200,
  seed: 42,

  turretX: 160,
  turretY: 185,
  turretAngle: 90,
  turretRotateSpeed: 3,       // deg/tick
  turretRadius: 8,

  projectileSpeed: 8,
  projectileRadius: 2,

  helicopterSpeed: 1.5,
  helicopterRadius: 12,
  helicopterSpawnInterval: 120,
  helicopterDropInterval: 60,
  helicopterMinY: 20,
  helicopterMaxY: 80,

  jetSpeed: 3.0,
  jetRadius: 10,
  jetSpawnInterval: 300,
  jetBombInterval: 90,

  paratrooperDescentRate: 0.5,
  paratrooperFreefallRate: 3.0,
  paratrooperRadius: 5,
  chuteRadius: 8,
  groundY: 190,

  bombFallRate: 2.0,
  bombRadius: 4,

  overrunThreshold: 4,

  scoreHelicopter: 150,
  scoreJet: 200,
  scoreParatrooper: 75,
  scoreBomb: 50,
  scoreShotCost: 1,
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

  input(action) {
    this._pendingInput = action;
  }

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
    if (this.tickCount < this._nextHelicopterTick) return;
    this._nextHelicopterTick = this.tickCount + this.cfg.helicopterSpawnInterval;

    const cfg = this.cfg;
    const fromLeft = this._rand() < 0.5;
    const y = cfg.helicopterMinY + this._rand() * (cfg.helicopterMaxY - cfg.helicopterMinY);
    const x = fromLeft ? -cfg.helicopterRadius : cfg.width + cfg.helicopterRadius;
    const direction = fromLeft ? 1 : -1;

    this.helicopters.push({
      id: this._id(),
      x, y,
      direction,
      speed: cfg.helicopterSpeed,
      state: 'active',
      _nextDropTick: this.tickCount + cfg.helicopterDropInterval,
    });
  }

  _spawnJets() {
    if (this.tickCount < this._nextJetTick) return;
    this._nextJetTick = this.tickCount + this.cfg.jetSpawnInterval;

    const cfg = this.cfg;
    const fromLeft = this._rand() < 0.5;
    const y = cfg.helicopterMinY + this._rand() * (cfg.helicopterMaxY - cfg.helicopterMinY);
    const x = fromLeft ? -cfg.jetRadius : cfg.width + cfg.jetRadius;
    const direction = fromLeft ? 1 : -1;

    this.jets.push({
      id: this._id(),
      x, y,
      direction,
      speed: cfg.jetSpeed,
      state: 'active',
      _nextBombTick: this.tickCount + cfg.jetBombInterval,
    });
  }

  _updateHelicopters() {
    const cfg = this.cfg;
    for (const h of this.helicopters) {
      if (h.state !== 'active') continue;

      h.x += h.direction * h.speed;

      // Drop paratrooper
      if (this.tickCount >= h._nextDropTick) {
        h._nextDropTick = this.tickCount + cfg.helicopterDropInterval;
        this.paratroopers.push({
          id: this._id(),
          x: h.x,
          y: h.y,
          state: 'chute',
          alive: true,
        });
      }

      // Exit screen
      if (h.x < -cfg.helicopterRadius * 2 || h.x > cfg.width + cfg.helicopterRadius * 2) {
        h.state = 'exiting';
      }
    }
    this.helicopters = this.helicopters.filter(h => h.state !== 'exiting');
  }

  _updateJets() {
    const cfg = this.cfg;
    for (const j of this.jets) {
      if (j.state !== 'active') continue;

      j.x += j.direction * j.speed;

      // Drop bomb
      if (this.tickCount >= j._nextBombTick) {
        j._nextBombTick = this.tickCount + cfg.jetBombInterval;
        this.bombs.push({ id: this._id(), x: j.x, y: j.y, state: 'falling', alive: true });
      }

      if (j.x < -cfg.jetRadius * 2 || j.x > cfg.width + cfg.jetRadius * 2) {
        j.state = 'exiting';
      }
    }
    this.jets = this.jets.filter(j => j.state !== 'exiting');
  }

  _updateParatroopers() {
    const cfg = this.cfg;
    for (const p of this.paratroopers) {
      if (p.state === 'dead' || p.state === 'landed') continue;

      if (p.state === 'chute') {
        p.y += cfg.paratrooperDescentRate;
      } else if (p.state === 'freefall') {
        p.y += cfg.paratrooperFreefallRate;
      }

      // Reached ground
      if (p.y >= cfg.groundY) {
        if (p.state === 'freefall') {
          // Kill any landed troopers in the same column
          for (const other of this.paratroopers) {
            if (other.state === 'landed' && Math.abs(other.x - p.x) <= cfg.paratrooperRadius * 2) {
              other.state = 'dead';
              if (other._side === 'left') this.landedLeft = Math.max(0, this.landedLeft - 1);
              else this.landedRight = Math.max(0, this.landedRight - 1);
            }
          }
          p.state = 'dead';
        } else {
          p.y = cfg.groundY;
          p.state = 'landed';
          if (p.x < cfg.turretX) {
            p._side = 'left';
            this.landedLeft++;
          } else {
            p._side = 'right';
            this.landedRight++;
          }
        }
      }
    }
  }

  _updateBombs() {
    const cfg = this.cfg;
    for (const b of this.bombs) {
      if (b.state !== 'falling') continue;
      b.y += cfg.bombFallRate;
      if (b.y > cfg.height) b.state = 'gone';
    }
    this.bombs = this.bombs.filter(b => b.state !== 'gone');
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

  _checkCollisions() {
    const cfg = this.cfg;

    for (const proj of this.projectiles) {
      if (!proj.alive) continue;

      // vs helicopters
      for (const h of this.helicopters) {
        if (h.state !== 'active') continue;
        if (dist(proj.x, proj.y, h.x, h.y) < cfg.helicopterRadius + cfg.projectileRadius) {
          proj.alive = false;
          h.state = 'destroyed';
          this.score += cfg.scoreHelicopter;
          break;
        }
      }
      if (!proj.alive) continue;

      // vs jets
      for (const j of this.jets) {
        if (j.state !== 'active') continue;
        if (dist(proj.x, proj.y, j.x, j.y) < cfg.jetRadius + cfg.projectileRadius) {
          proj.alive = false;
          j.state = 'destroyed';
          this.score += cfg.scoreJet;
          break;
        }
      }
      if (!proj.alive) continue;

      // vs bombs
      for (const b of this.bombs) {
        if (b.state !== 'falling') continue;
        if (dist(proj.x, proj.y, b.x, b.y) < cfg.bombRadius + cfg.projectileRadius) {
          proj.alive = false;
          b.state = 'destroyed';
          this.score += cfg.scoreBomb;
          break;
        }
      }
      if (!proj.alive) continue;

      // vs paratroopers
      for (const p of this.paratroopers) {
        if (p.state !== 'chute' && p.state !== 'freefall') continue;

        // Hit chute (above body) — only when descending with chute
        if (p.state === 'chute') {
          const chuteY = p.y - cfg.paratrooperRadius - cfg.chuteRadius / 2;
          if (dist(proj.x, proj.y, p.x, chuteY) < cfg.chuteRadius + cfg.projectileRadius) {
            proj.alive = false;
            p.state = 'freefall';
            break;
          }
        }

        // Hit body
        if (dist(proj.x, proj.y, p.x, p.y) < cfg.paratrooperRadius + cfg.projectileRadius) {
          proj.alive = false;
          p.state = 'dead';
          this.score += cfg.scoreParatrooper;
          break;
        }
      }
    }

    this.projectiles = this.projectiles.filter(p => p.alive);
    this.helicopters = this.helicopters.filter(h => h.state !== 'destroyed');
    this.jets = this.jets.filter(j => j.state !== 'destroyed');

    // Bombs vs turret
    for (const b of this.bombs) {
      if (b.state !== 'falling') continue;
      if (dist(b.x, b.y, this.turret.x, this.turret.y) < cfg.bombRadius + cfg.turretRadius) {
        b.state = 'destroyed';
        this.turret.alive = false;
        this.over = true;
        this.outcome = 'bomb_hit';
      }
    }
  }

  _checkLoseConditions() {
    if (this.over) return;
    if (this.landedLeft >= this.cfg.overrunThreshold) {
      this.over = true;
      this.outcome = 'overrun_left';
    } else if (this.landedRight >= this.cfg.overrunThreshold) {
      this.over = true;
      this.outcome = 'overrun_right';
    }
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
