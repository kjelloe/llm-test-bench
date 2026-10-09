// boombrawl client/input.js (commit e807b68), keyboard part. The touch joystick that follows is omitted.
// client/input.js — touch + keyboard → held-direction intents and bomb
// presses. Emits onDir(dx, dy) only on change; the predictor holds the
// current intent between changes.
const KEYMAP = {
  KeyW: [0, -1], ArrowUp: [0, -1],
  KeyS: [0, 1], ArrowDown: [0, 1],
  KeyA: [-1, 0], ArrowLeft: [-1, 0],
  KeyD: [1, 0], ArrowRight: [1, 0]
};
const DEAD_PX = 16; // joystick deadzone

export function createInput({ sceneEl, bombEl, trigEl, joyBase, joyKnob, onDir, onBomb, onTrigger, onTap }) {
  let cur = [0, 0];
  const emit = (dx, dy) => {
    if (cur[0] === dx && cur[1] === dy) return;
    cur = [dx, dy];
    onDir(dx, dy);
  };

  const typing = () => {
    const el = document.activeElement;
    return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA');
  };

  // Keyboard: last-pressed wins, releases fall back to what's still held.
  const held = [];
  document.addEventListener('keydown', e => {
    if (typing()) return;
    if (e.code === 'Space' || e.code === 'KeyE') {
      e.preventDefault();
      if (!e.repeat) onBomb();
      return;
    }
    if (e.code === 'KeyR') {
      e.preventDefault();
      if (!e.repeat) onTrigger();
      return;
    }
    const dir = KEYMAP[e.code];
    if (!dir) return;
    e.preventDefault();
    if (e.repeat) return;
    const i = held.indexOf(e.code);
    if (i !== -1) held.splice(i, 1);
    held.unshift(e.code);
    emit(...dir);
  });
  document.addEventListener('keyup', e => {
    const i = held.indexOf(e.code);
    if (i === -1) return;
    held.splice(i, 1);
    if (held.length) emit(...KEYMAP[held[0]]);
    else emit(0, 0);
  });
  window.addEventListener('blur', () => {
    held.length = 0;
    emit(0, 0);
  });
  // ... touch joystick ...
}
