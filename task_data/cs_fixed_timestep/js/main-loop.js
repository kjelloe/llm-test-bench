// Excerpt of boombrawl client/main.js (real code): a 20 Hz input tick drives prediction, rAF drives the renderer.
import { TICK_MS } from '#shared/const.mjs';   // TICK_HZ = 20, TICK_MS = 1000 / TICK_HZ

setInterval(() => {
  if (session.id) pred.tick();
}, TICK_MS);


function loop(t) {
  renderer.frame(t, {
    sample: interp.sample(t),
    latest: interp.latest(),
    meId: session.id,
    mePos: pred.isActive() ? pred.pos() : null
  });
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
