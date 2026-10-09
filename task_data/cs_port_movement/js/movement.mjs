// shared/movement.mjs — the one movement integrator. The server tick and the
// client's own-player prediction both run this verbatim; any drift between
// them becomes a visible rubber-band, so all world knowledge arrives through
// the blocked(cx, cy) callback and nothing else.
import { CELL, HALF, BODY, ASSIST_MIN } from './const.mjs';
import { worldToCell, clamp } from './fixedmath.mjs';

// One tick of movement. dirX/dirY in {-1,0,1}, single axis (the input mapper
// guarantees it; if both arrive, x wins). Returns the new {x, y}.
export function stepEntity(x, y, dirX, dirY, speed, blocked) {
  if (dirX !== 0) return stepAxis(x, y, dirX, speed, blocked, true);
  if (dirY !== 0) return stepAxis(x, y, dirY, speed, blocked, false);
  return { x, y };
}

// u = coordinate along the movement axis, v = perpendicular ("lane") one.
function stepAxis(x, y, sign, speed, blocked, horizontal) {
  let u = horizontal ? x : y;
  let v = horizontal ? y : x;
  const cv = worldToCell(v);
  const isBlocked = (au, av) => (horizontal ? blocked(au, av) : blocked(av, au));

  const lead = u + sign * (speed + BODY);
  const target = worldToCell(lead);
  if (target === worldToCell(u) || !isBlocked(target, cv)) {
    u += sign * speed;
    // Glide toward the corridor centre so the next turn lands cleanly.
    v += clamp(cv * CELL + HALF - v, -speed, speed);
  } else {
    // Flush against the wall face...
    u = sign > 0 ? target * CELL - BODY - 1 : (target + 1) * CELL + BODY;
    // ...but slide around the corner when the player is leaning into an
    // open lane (the forgiveness that makes mobile corridors playable).
    const offset = v - (cv * CELL + HALF);
    if (offset >= ASSIST_MIN && !isBlocked(target, cv + 1)) {
      v += Math.min(speed, (cv + 1) * CELL + HALF - v);
    } else if (offset <= -ASSIST_MIN && !isBlocked(target, cv - 1)) {
      v -= Math.min(speed, v - ((cv - 1) * CELL + HALF));
    }
  }
  return horizontal ? { x: u, y: v } : { x: v, y: u };
}
