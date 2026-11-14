//! Reference port of js/fixedmath.mjs, js/movement.mjs and js/rng.mjs.
pub const CELL: i32 = 256;
pub const HALF: i32 = 128;
pub const BODY: i32 = 108;
pub const ASSIST_MIN: i32 = 64;

pub fn world_to_cell(w: i32) -> i32 {
    w.div_euclid(CELL)
}

pub fn cell_to_world(c: i32) -> i32 {
    c * CELL + HALF
}

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
    let mut u = if horizontal { x } else { y };
    let mut v = if horizontal { y } else { x };
    let cv = world_to_cell(v);
    let is_blocked = |au: i32, av: i32| if horizontal { blocked(au, av) } else { blocked(av, au) };
    let lead = u + sign * (speed + BODY);
    let target = world_to_cell(lead);
    if target == world_to_cell(u) || !is_blocked(target, cv) {
        u += sign * speed;
        v += (cv * CELL + HALF - v).clamp(-speed, speed);
    } else {
        u = if sign > 0 { target * CELL - BODY - 1 } else { (target + 1) * CELL + BODY };
        let offset = v - (cv * CELL + HALF);
        if offset >= ASSIST_MIN && !is_blocked(target, cv + 1) {
            v += speed.min((cv + 1) * CELL + HALF - v);
        } else if offset <= -ASSIST_MIN && !is_blocked(target, cv - 1) {
            v -= speed.min(v - ((cv - 1) * CELL + HALF));
        }
    }
    if horizontal { (u, v) } else { (v, u) }
}

pub struct XorShift32 {
    seed: u32,
}

impl XorShift32 {
    pub fn new(seed: u32) -> Self {
        XorShift32 { seed }
    }

    pub fn next_u32(&mut self) -> u32 {
        let mut s = self.seed;
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        self.seed = s;
        s
    }

    pub fn next_f64(&mut self) -> f64 {
        self.next_u32() as f64 / 4294967296.0
    }
}
