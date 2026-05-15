// Paratrooper (1982) — headless game backend
// Implement the Game class below.
//
// Coordinate system: (0,0) top-left, x right, y down, 320×200
// Turret angle: 0 = hard left, 90 = straight up, 180 = hard right
// Tick rate: speeds in px/tick, no wall-clock
//
// Required API:
//   new Game(config)        — construct with optional config overrides
//   game.input(action)      — queue action for next tick: 'rotate_left' | 'rotate_right' | 'fire' | 'none'
//   game.tick()             — advance one frame (apply input, move entities, check collisions)
//   game.getState()         — return snapshot (see structure below)
//   game.isOver()           — return boolean
//   game.getResult()        — return { outcome, score, landedLeft, landedRight }
//
// getState() must return:
//   { tick, score, turret: {x,y,angleDeg,alive}, landedLeft, landedRight,
//     helicopters, jets, paratroopers, bombs, projectiles, over, outcome }
//
// Default config values (all overridable):
//   width:320, height:200, seed:42
//   turretX:160, turretY:185, turretAngle:90, turretRotateSpeed:3, turretRadius:8
//   projectileSpeed:8, projectileRadius:2
//   helicopterSpeed:1.5, helicopterRadius:12
//   helicopterSpawnInterval:120, helicopterDropInterval:60
//   helicopterMinY:20, helicopterMaxY:80
//   jetSpeed:3.0, jetRadius:10, jetSpawnInterval:300, jetBombInterval:90
//   paratrooperDescentRate:0.5, paratrooperFreefallRate:3.0
//   paratrooperRadius:5, chuteRadius:8, groundY:190
//   bombFallRate:2.0, bombRadius:4
//   overrunThreshold:4
//   scoreHelicopter:150, scoreJet:200, scoreParatrooper:75, scoreBomb:50, scoreShotCost:1
//
// Game rules:
//   - Helicopters fly across the screen dropping paratroopers at helicopterDropInterval ticks.
//   - Paratroopers descend in 'chute' state at paratrooperDescentRate px/tick.
//   - Shooting a parachute converts the paratrooper to 'freefall' (faster descent).
//   - Shooting a paratrooper body (or freefall) sets state to 'dead' and awards scoreParatrooper.
//   - A freefall paratrooper landing on a landed paratrooper kills the landed one
//     and decrements the appropriate landedLeft/landedRight counter.
//   - Paratroopers landing left of turretX increment landedLeft; right increments landedRight.
//   - Game ends immediately (outcome:'overrun_left'/'overrun_right') when either side reaches overrunThreshold.
//   - Jets fly faster than helicopters and drop bombs.
//   - Bombs fall at bombFallRate; hitting the turret ends the game (outcome:'bomb_hit').
//   - Shooting a bomb destroys it and awards scoreBomb.
//   - Every fire action costs scoreShotCost points (score can go negative).
//   - game.tick() does nothing if isOver() is true.
//   - RNG must use the provided seed for deterministic spawning.

export class Game {
  constructor(config = {}) {
    // TODO: implement
  }

  input(action) {
    // TODO: implement
  }

  tick() {
    // TODO: implement
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
    // TODO: implement
    return {
      tick: 0, score: 0,
      turret: { x: 160, y: 185, angleDeg: 90, alive: true },
      landedLeft: 0, landedRight: 0,
      helicopters: [], jets: [], paratroopers: [], bombs: [], projectiles: [],
      over: false, outcome: null,
    };
  }
}
