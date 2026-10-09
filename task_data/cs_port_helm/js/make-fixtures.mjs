// Prints tests/GameClientTests/fixtures.json: scripted sessions replayed through the real helm code
// (js/helm.mjs), recording every message sent and the helm state after each step.
// Run: node js/make-fixtures.mjs > tests/GameClientTests/fixtures.json
import * as helm from './helm.mjs';

function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function session(seed) {
  const rnd = mulberry32(seed);
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const s = helm.state;
  Object.assign(s, { view: undefined, carrierId: -1, throttle: 0, rudder: 0, climb: 0, selectedUnitId: -1, piloting: false });
  let sent = [];
  s.transport = { send: (m) => sent.push(m) };
  const units = new Map();
  let nextId = 10;
  let shipThrottle = 0, shipRudder = 0;
  const steps = [];
  const record = (op) => {
    steps.push({ op, sent, state: { throttle: s.throttle, rudder: s.rudder, climb: s.climb,
      selectedUnitId: s.selectedUnitId, piloting: s.piloting, carrierId: s.carrierId } });
    sent = [];
  };
  for (let i = 0; i < 45; i++) {
    const r = rnd();
    if (i === 0 || r < 0.22) {
      // A new view: units come and go and change state; the server reports its own helm figures.
      if (rnd() < 0.5) units.set(nextId, { id: nextId++, team: rnd() < 0.8 ? 0 : 1, kind: pick([0, 0, 1, 1, 2, 3, 4]), state: 1 });
      for (const u of units.values()) {
        const q = rnd();
        if (q < 0.12) units.delete(u.id);
        else if (q < 0.3) u.state = pick([0, 1, 2, 3, 4, 5]);
      }
      if (rnd() < 0.5) { shipThrottle = pick([-25, -10, 0, 20, 50, 100]); shipRudder = pick([-1, 0, 1]); }
      const view = {
        team: 0,
        carriers: [
          { id: 1, team: 0, contact: i === 0 && seed % 4 === 0 ? 1 : 0, throttle: shipThrottle, rudder: shipRudder },
          { id: 2, team: 1, contact: 0, throttle: 40, rudder: 0 },
        ],
        units: [...units.values()].map((u) => ({ ...u })),
      };
      helm.onSnapshot({ view });
      record({ op: 'view', view });
      continue;
    }
    const op = pick(['w', 'w', 's', 's', 'x', 'rudder', 'rudder', 'climb', 'cycle', 'launch', 'pilot', 'pilot', 'escort', 'recall']);
    switch (op) {
      case 'w': case 's': case 'x': helm.keys[op](); record({ op }); break;
      case 'rudder': { const v = pick([-1, 0, 1]); helm.sendRudder(v); record({ op, value: v }); break; }
      case 'climb': { const v = pick([-1, 0, 1]); helm.sendClimb(v); record({ op, value: v }); break; }
      case 'cycle': helm.cycleSelection(); record({ op }); break;
      case 'launch': { const k = pick([0, 1, 2]); helm.launch(k); record({ op, kind: k }); break; }
      case 'pilot': helm.togglePiloting(); record({ op }); break;
      case 'escort': helm.orderEscort(); record({ op }); break;
      case 'recall': helm.recallSelected(); record({ op }); break;
    }
  }
  return { seed, steps };
}

const sessions = [];
for (let seed = 1; seed <= 40; seed++) sessions.push(session(seed));
process.stdout.write(JSON.stringify({ sessions }) + '\n');
