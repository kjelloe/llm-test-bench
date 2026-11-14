//! Picks captured from the browser (fixtures/picks.txt, see tools/make_fixtures.reference.py): the game's camera
//! (vertical fov 58 degrees) at five poses, a grid of clicks over the viewport, and three's answer.
use pick_sea::pick::{js_round, pick_sea, Camera};

struct Pick {
    camera: Camera,
    ndc: (f64, f64),
    hit: Option<(i64, i64)>,
}

fn picks() -> Vec<Pick> {
    include_str!("../fixtures/picks.txt")
        .lines()
        .map(|l| {
            let t: Vec<&str> = l.split_whitespace().collect();
            let f = |i: usize| t[i].parse::<f64>().unwrap();
            Pick {
                camera: Camera { eye: [f(0), f(1), f(2)], target: [f(3), f(4), f(5)], fov_degrees: 58.0, aspect: f(6) },
                ndc: (f(7), f(8)),
                hit: if t[9] == "miss" { None } else { Some((t[9].parse().unwrap(), t[10].parse().unwrap())) },
            }
        })
        .collect()
}

fn check(filter: impl Fn(&Pick) -> bool) {
    let all = picks();
    let chosen: Vec<&Pick> = all.iter().filter(|p| filter(p)).collect();
    assert!(!chosen.is_empty());
    let bad: Vec<String> = chosen
        .iter()
        .filter_map(|p| {
            let got = pick_sea(&p.camera, p.ndc.0, p.ndc.1);
            (got != p.hit).then(|| format!("eye {:?} target {:?} ndc {:?}: {:?}, three gives {:?}", p.camera.eye, p.camera.target, p.ndc, got, p.hit))
        })
        .collect();
    assert!(bad.is_empty(), "{} of {} picks differ, first: {:?}", bad.len(), chosen.len(), &bad[..bad.len().min(3)]);
}

#[test]
fn js_round_sends_halves_up() {
    assert_eq!(js_round(2.5), 3.0);
    assert_eq!(js_round(-2.5), -2.0);
    assert_eq!(js_round(-0.5), 0.0);
    assert_eq!(js_round(-2.51), -3.0);
    assert_eq!(js_round(7.49), 7.0);
}

#[test]
fn the_centre_of_the_view_hits_where_the_camera_looks() {
    let c = Camera { eye: [0.0, 400.0, 0.0], target: [800.0, 0.0, -300.0], fov_degrees: 58.0, aspect: 1.5 };
    assert_eq!(pick_sea(&c, 0.0, 0.0), Some((204800, 76800)));
}

#[test]
fn hits_from_the_bridge_view() {
    check(|p| p.camera.eye == [0.0, 400.0, 0.0] && p.hit.is_some());
}

#[test]
fn hits_from_the_high_chart_view() {
    check(|p| p.camera.eye == [5000.0, 7000.0, -3800.0] && p.hit.is_some());
}

#[test]
fn hits_from_low_and_oblique_cameras() {
    check(|p| p.camera.eye[1] < 1000.0 && p.camera.eye != [0.0, 400.0, 0.0] && p.hit.is_some());
}

#[test]
fn clicks_at_the_sky_miss() {
    check(|p| p.hit.is_none());
}

#[test]
fn every_captured_pick() {
    check(|_| true);
}
