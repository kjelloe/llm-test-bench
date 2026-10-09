// Helm and selection commands from CarrierDominion client/main.js (commit 4005e3a), VERBATIM except where
// marked "// (omitted: ...)": HUD text and the 3D follow camera are left out, they send nothing.
// ownCarrierOf is from client/render/scene.js; onSnapshot keeps only its helm part. Key bindings
// (main.js): w = sendThrottle(state.throttle + THROTTLE_STEP), s = sendThrottle(state.throttle -
// THROTTLE_STEP), x = sendThrottle(0); A/D send rudder 1/-1, release sends 0; arrows send climb 1/-1/0.

const THROTTLE_STEP = 10;
const KIND_MANTA = 0;
const KIND_WALRUS = 1;
const UNIT_ACTIVE = 1;
const UNIT_RETURNING = 2;
// A Manta parked on an island runway is still 'out' for the chips.
const UNIT_LANDED_STATE = 4;

export const state = {
  view: undefined,
  carrierId: -1,
  throttle: 0,
  rudder: 0,
  climb: 0,
  selectedUnitId: -1,
  piloting: false,
  transport: { send: () => {} },
};

function ownCarrierOf(view) {
  for (const carrier of view.carriers) {
    if (carrier.team === view.team && carrier.contact === 0) return carrier;
  }
  return undefined;
}

function afloatUnits() {
  if (state.view === undefined) return [];
  return state.view.units.filter(
    (unit) => unit.team === state.view.team
      && (unit.state === UNIT_ACTIVE || unit.state === UNIT_RETURNING
        || unit.state === UNIT_LANDED_STATE),
  );
}

// What NEXT and the chips will actually NAME: the hulls a commander flies.
// The lighter runs its own errand, the aerostat has no stick, the decoys
// are a screen - selecting any of them would only turn the next click on
// open water into an order for something that never wanted one. This
// matters from the first second now: with a home island the supply boat is
// afloat at tick 1, and it used to grab the selection before the player had
// touched anything, turning click-to-sail into click-to-move-the-boat.
function selectableUnits() {
  return afloatUnits().filter((unit) => unit.kind === KIND_MANTA || unit.kind === KIND_WALRUS);
}

function selectedUnit() {
  return afloatUnits().find((unit) => unit.id === state.selectedUnitId);
}

// The SHIP has an astern gear down to -25 (the bottom quarter of the scale,
// as 1988 had it); a craft's throttle stays 0..100.
function clampThrottle(value, floor) {
  return Math.max(floor, Math.min(100, value));
}

// W/S and A/D drive whatever the player is currently at the controls of: the
// piloted unit if there is one, otherwise the carrier's helm.
function sendThrottle(next) {
  if (state.piloting) {
    const wanted = clampThrottle(next, 0);
    const unit = selectedUnit();
    if (unit === undefined) return;
    state.throttle = wanted;
    state.transport.send({
      type: 'set_unit_helm', unitId: unit.id, throttle: wanted, rudder: state.rudder,
      climb: state.climb,
    });
    return;
  }
  const wanted = clampThrottle(next, -25);
  if (wanted === state.throttle || state.carrierId < 0) return;
  state.throttle = wanted;
  state.transport.send({ type: 'set_throttle', carrierId: state.carrierId, throttle: wanted });
}

function sendRudder(next) {
  if (state.piloting) {
    const unit = selectedUnit();
    if (unit === undefined || next === state.rudder) return;
    state.rudder = next;
    state.transport.send({
      type: 'set_unit_helm', unitId: unit.id, throttle: state.throttle, rudder: next,
      climb: state.climb,
    });
    return;
  }
  if (next === state.rudder || state.carrierId < 0) return;
  state.rudder = next;
  state.transport.send({ type: 'set_rudder', carrierId: state.carrierId, rudder: next });
}

// The stick's vertical axis: only a piloted aircraft has one. Held keys, like
// the rudder - release and the nose levels.
function sendClimb(next) {
  if (!state.piloting) return;
  const unit = selectedUnit();
  if (unit === undefined || next === state.climb) return;
  state.climb = next;
  state.transport.send({
    type: 'set_unit_helm', unitId: unit.id, throttle: state.throttle, rudder: state.rudder,
    climb: next,
  });
}

function cycleSelection() {
  const units = selectableUnits();
  if (units.length === 0) {
    state.selectedUnitId = -1;
    return;
  }
  const index = units.findIndex((unit) => unit.id === state.selectedUnitId);
  state.selectedUnitId = units[(index + 1) % units.length].id;
}

function launch(kind) {
  if (state.carrierId < 0) return;
  state.transport.send({ type: 'launch_unit', carrierId: state.carrierId, kind: kind });
}

// Escort: the selected unit takes station on the ship and fights what comes.
function orderEscort() {
  const unit = selectedUnit();
  if (unit === undefined) return;
  stopPiloting();
  state.transport.send({ type: 'order_unit_escort', unitId: unit.id });
  // (omitted: HUD status text)
}

function recallSelected() {
  const unit = selectedUnit();
  if (unit === undefined) return;
  stopPiloting();
  state.transport.send({ type: 'recall_unit', unitId: unit.id });
}

function stopPiloting() {
  if (!state.piloting) return;
  const unit = selectedUnit();
  state.piloting = false;
  // (omitted: 3D follow camera)
  if (unit !== undefined) state.transport.send({ type: 'release_control', unitId: unit.id });
  const carrier = ownCarrierOf(state.view);
  state.throttle = carrier === undefined ? 0 : carrier.throttle;
  state.rudder = 0;
  state.climb = 0;
}

function togglePiloting() {
  if (state.piloting) {
    stopPiloting();
    return;
  }
  const unit = selectedUnit();
  if (unit === undefined) return;
  state.piloting = true;
  state.throttle = 100;
  state.rudder = 0;
  state.climb = 0;
  // (omitted: 3D follow camera)
  state.transport.send({ type: 'take_control', unitId: unit.id });
}

// From onSnapshot (client/main.js): the helm part only.
export function onSnapshot(message) {
  state.view = message.view;
  // (omitted: world reset, sound, signals, probes, weather override, stateHash)
  const own = ownCarrierOf(message.view);
  if (own !== undefined) {
    state.carrierId = own.id;
    // The server is the authority on the helm; adopt what it reports so a
    // rejected or lost command cannot leave the HUD lying.
    if (!state.piloting) {
      state.throttle = own.throttle;
      state.rudder = own.rudder;
    }
  }
  // A selection that has been recovered, lost, or shot down stops being one.
  if (state.selectedUnitId !== -1 && selectedUnit() === undefined) {
    state.selectedUnitId = -1;
    state.piloting = false;
    // (omitted: 3D follow camera)
  }
  if (state.selectedUnitId === -1 && selectableUnits().length > 0) cycleSelection();
}

export const keys = {
  w: () => sendThrottle(state.throttle + THROTTLE_STEP),
  s: () => sendThrottle(state.throttle - THROTTLE_STEP),
  x: () => sendThrottle(0),
};

export { sendRudder, sendClimb, cycleSelection, launch, orderEscort, recallSelected, togglePiloting };
