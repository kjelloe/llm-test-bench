// client/sound.js — synthesized effects, zero assets. WebAudio unlocks on
// the first user gesture (mobile requirement); every effect is a short
// oscillator/noise envelope so there is nothing to download or license.
export function createSound() {
  let ctx = null;
  let muted = false;
  try {
    muted = localStorage.getItem('bb-muted') === '1';
  } catch (e) { /* fine */ }

  function ensure() {
    if (muted) return null;
    try {
      if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') ctx.resume();
      return ctx;
    } catch (e) {
      return null;
    }
  }

  // One oscillator with a decay envelope; optional pitch slide.
  function tone(freq, dur, { type = 'square', vol = 0.15, slideTo = 0, at = 0 } = {}) {
    const c = ensure();
    if (!c) return;
    const t0 = c.currentTime + at;
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (slideTo) osc.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t0 + dur);
    gain.gain.setValueAtTime(vol, t0);
    gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
    osc.connect(gain).connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  }

  // Filtered noise burst — the body of every explosion.
  function noise(dur, { vol = 0.3, freq = 500, at = 0 } = {}) {
    const c = ensure();
    if (!c) return;
    const t0 = c.currentTime + at;
    const len = Math.ceil(c.sampleRate * dur);
    const buf = c.createBuffer(1, len, c.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    const src = c.createBufferSource();
    src.buffer = buf;
    const filter = c.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(freq * 2, t0);
    filter.frequency.exponentialRampToValueAtTime(Math.max(40, freq / 4), t0 + dur);
    const gain = c.createGain();
    gain.gain.setValueAtTime(vol, t0);
    gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
    src.connect(filter).connect(gain).connect(c.destination);
    src.start(t0);
  }

  return {
    unlock: () => { ensure(); },
    isMuted: () => muted,
    toggleMute() {
      muted = !muted;
      try {
        localStorage.setItem('bb-muted', muted ? '1' : '0');
      } catch (e) { /* fine */ }
      if (!muted) ensure();
      return muted;
    },
    // countdown blip (last seconds before the round)
    tick: () => tone(880, 0.07, { vol: 0.12 }),
    // round start
    go: () => {
      tone(440, 0.12, { vol: 0.18 });
      tone(660, 0.12, { at: 0.11, vol: 0.18 });
      tone(880, 0.22, { at: 0.22, vol: 0.2 });
    },
    // bomb explosion
    boom: () => {
      noise(0.35, { vol: 0.3, freq: 420 });
      tone(120, 0.3, { type: 'sine', vol: 0.35, slideTo: 38 });
    },
    // you died
    death: () => {
      tone(420, 0.5, { type: 'sawtooth', vol: 0.2, slideTo: 70 });
      noise(0.25, { vol: 0.12, freq: 300, at: 0.08 });
    },
    // shrink alarm
    shrink: () => {
      tone(330, 0.12, { vol: 0.14 });
      tone(220, 0.16, { at: 0.14, vol: 0.14 });
    },
    // round end fanfare
    win: () => {
      tone(523, 0.14, { vol: 0.16 });
      tone(659, 0.14, { at: 0.13, vol: 0.16 });
      tone(784, 0.3, { at: 0.26, vol: 0.18 });
    }
  };
}
