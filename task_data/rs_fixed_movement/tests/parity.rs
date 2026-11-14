//! Fixtures come from the game's own JavaScript (tools/make_fixtures.reference.mjs over js/).
use fixed_movement::fixed::*;

const ARENA: &str = include_str!("../js/arena.txt");
const MOVEMENT: &str = include_str!("../fixtures/movement.txt");
const CELLS: &str = include_str!("../fixtures/world_to_cell.txt");
const RNG: &str = include_str!("../fixtures/rng.txt");

fn nums(line: &str) -> Vec<f64> {
    line.split_whitespace().map(|t| t.parse::<f64>().unwrap()).collect()
}

fn blocked(cx: i32, cy: i32) -> bool {
    let grid = ARENA.trim().as_bytes();
    cx < 0 || cy < 0 || cx >= 25 || cy >= 17 || grid[(cy * 25 + cx) as usize] != b'.'
}

fn steps(filter: impl Fn(usize) -> bool) {
    let mut bad = Vec::new();
    for (i, line) in MOVEMENT.lines().enumerate().filter(|(i, _)| filter(*i)) {
        let r: Vec<i32> = nums(line).iter().map(|&v| v as i32).collect();
        let got = step_entity(r[0], r[1], r[2], r[3], r[4], &blocked);
        if got != (r[5], r[6]) {
            bad.push(format!("line {}: step({}, {}, {}, {}, {}) = {:?}, JS gives ({}, {})", i + 1, r[0], r[1], r[2], r[3], r[4], got, r[5], r[6]));
        }
    }
    assert!(bad.is_empty(), "{} of the steps differ from the JS, first: {:?}", bad.len(), &bad[..bad.len().min(5)]);
}

#[test]
fn world_to_cell_is_js_math_floor_for_every_sign() {
    for line in CELLS.lines() {
        let r = nums(line);
        assert_eq!(world_to_cell(r[0] as i32), r[1] as i32, "worldToCell({})", r[0]);
    }
}

#[test]
fn cell_to_world_is_the_cell_centre() {
    assert_eq!(cell_to_world(0), 128);
    assert_eq!(cell_to_world(-1), -128);
    assert_eq!(cell_to_world(24), 6272);
}

#[test]
fn wall_approaches_match_the_js_step_for_step() {
    let n = MOVEMENT.lines().count();
    steps(|i| i < n - 3002);
}

#[test]
fn seeded_walks_match_the_js_step_for_step() {
    let n = MOVEMENT.lines().count();
    steps(|i| i >= n - 3002 && i < n - 2);
}

#[test]
fn both_directions_at_once_x_wins() {
    let n = MOVEMENT.lines().count();
    steps(|i| i >= n - 2);
}

#[test]
fn xorshift_u32_matches_the_js() {
    let mut rng = None;
    for line in RNG.lines() {
        let t: Vec<&str> = line.split_whitespace().collect();
        let (seed, i, u): (u32, usize, u32) = (t[0].parse().unwrap(), t[1].parse().unwrap(), t[2].parse().unwrap());
        if i == 0 {
            rng = Some(XorShift32::new(seed));
        }
        assert_eq!(rng.as_mut().unwrap().next_u32(), u, "seed {seed} value {i}");
    }
}

#[test]
fn xorshift_f64_matches_the_js() {
    let mut rng = None;
    for line in RNG.lines() {
        let t: Vec<&str> = line.split_whitespace().collect();
        let (seed, i, f): (u32, usize, f64) = (t[0].parse().unwrap(), t[1].parse().unwrap(), t[3].parse().unwrap());
        if i == 0 {
            rng = Some(XorShift32::new(seed));
        }
        assert_eq!(rng.as_mut().unwrap().next_f64().to_bits(), f.to_bits(), "seed {seed} value {i}");
    }
}
