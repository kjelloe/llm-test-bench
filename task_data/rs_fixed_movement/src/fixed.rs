//! First Rust port of the game's fixed-point helpers, movement integrator and seeded random source
//! (js/fixedmath.mjs, js/movement.mjs, js/rng.mjs). The server runs the JavaScript; this port runs the
//! native client's own-player prediction, so it must give the same integers as the JavaScript for every
//! input, or the player rubber-bands. Keep the public API; make it match the JavaScript bit for bit.
pub const CELL: i32 = 256;
pub const HALF: i32 = 128;
pub const BODY: i32 = 108;
pub const ASSIST_MIN: i32 = 64;

/// `Math.floor(w / CELL)`.
pub fn world_to_cell(w: i32) -> i32 {
    w / CELL
}

pub fn cell_to_world(c: i32) -> i32 {
    c * CELL + HALF
}

/// One tick of movement; dir_x/dir_y in {-1, 0, 1}, x wins if both are set.
pub fn step_entity(x: i32, y: i32, dir_x: i32, dir_y: i32, speed: i32, blocked: &dyn Fn(i32, i32) -> bool) -> (i32, i32) {
    if dir_x != 0 {
        return step_axis(x, y, dir_x, speed, blocked, true);
    }
    if dir_y != 0 {
        return step_axis(x, y, dir_y, speed, blocked, false);
    }
    (x, y)
}

fn step_axis(x: i32, y: i32, sign: i32, speed: i32, blocked: &dyn Fn(i32, i32) -> bool, horizontal: bool) -> (i32, i32) {
    let (mut u, mut v) = if horizontal { (x as f32, y as f32) } else { (y as f32, x as f32) };
    let cv = world_to_cell(v as i32);
    let is_blocked = |au: i32, av: i32| if horizontal { blocked(au, av) } else { blocked(av, au) };
    let lead = u + (sign * (speed + BODY)) as f32;
    let target = world_to_cell(lead as i32);
    if target == world_to_cell(u as i32) || !is_blocked(target, cv) {
        u += (sign * speed) as f32;
        let centre = (cv * CELL + HALF) as f32;
        v += (centre - v).clamp(-speed as f32, speed as f32) * 0.5;
    } else {
        u = if sign > 0 { (target * CELL - BODY - 1) as f32 } else { ((target + 1) * CELL + BODY) as f32 };
        let offset = v - (cv * CELL + HALF) as f32;
        if offset > ASSIST_MIN as f32 && !is_blocked(target, cv + 1) {
            v += (speed as f32).min(((cv + 1) * CELL + HALF) as f32 - v);
        } else if offset < -ASSIST_MIN as f32 && !is_blocked(target, cv - 1) {
            v -= (speed as f32).min(v - ((cv - 1) * CELL + HALF) as f32);
        }
    }
    if horizontal { (u as i32, v as i32) } else { (v as i32, u as i32) }
}

/// js/rng.mjs's xorshift32.
pub struct XorShift32 {
    seed: i32,
}

impl XorShift32 {
    pub fn new(seed: u32) -> Self {
        XorShift32 { seed: seed as i32 }
    }

    pub fn next_u32(&mut self) -> u32 {
        let mut s = self.seed;
        s ^= s.wrapping_shl(13);
        s ^= s >> 17;
        s ^= s.wrapping_shl(5);
        self.seed = s;
        s as u32
    }

    pub fn next_f64(&mut self) -> f64 {
        (self.next_u32() as f32 / 4294967296.0) as f64
    }
}
