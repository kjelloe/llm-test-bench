use ecs_frame::ecs::*;
use ecs_frame::game::{self, CLEAR_SKY_LUX, TEAM_COLORS};

fn hull(app: &mut App, team: u8, x: f32, heave: f32) -> usize {
    let h = app.world.materials.add(Material { color: [0.8, 0.8, 0.8] });
    app.world.entities.push(Entity {
        sim: Some(Vec3 { x, y: 0.0, z: 0.0 }),
        transform: Some(Vec3::default()),
        team: Some(team),
        material: Some(h),
        heave: Some(heave),
        ..Default::default()
    });
    app.world.entities.len() - 1
}

fn sun(app: &mut App) -> usize {
    app.world.entities.push(Entity { sun: Some(Sun { illuminance: 0.0 }), light_base: Some(LightBase { lux: CLEAR_SKY_LUX }), ..Default::default() });
    app.world.entities.len() - 1
}

fn app() -> App {
    let mut app = App::new();
    game::register(&mut app);
    app
}

fn frames(app: &mut App, n: usize, start: f64) {
    for i in 0..n {
        app.update(start + i as f64 / 60.0);
    }
}

#[test]
fn hulls_show_their_team_colour() {
    let mut a = app();
    let (h0, h1) = (hull(&mut a, 0, 0.0, 0.0), hull(&mut a, 1, 5.0, 0.0));
    frames(&mut a, 2, 0.0);
    let m = |i: usize| a.world.materials.get(a.world.entities[i].material.unwrap()).color;
    assert_eq!((m(h0), m(h1)), (TEAM_COLORS[0], TEAM_COLORS[1]));
}

#[test]
fn unchanged_materials_are_not_uploaded_every_frame() {
    let mut a = app();
    for i in 0..20 {
        hull(&mut a, (i % 2) as u8, i as f32, 0.0);
    }
    frames(&mut a, 30, 0.0);
    let uploads: Vec<usize> = a.world.drawn.iter().map(|d| d.uploads).collect();
    assert_eq!(uploads[0], 20, "the first frame uploads every new material");
    assert!(uploads[2..].iter().all(|&u| u == 0), "uploads per frame: {uploads:?}");
}

#[test]
fn a_team_change_uploads_exactly_that_material() {
    let mut a = app();
    let hs: Vec<usize> = (0..6).map(|i| hull(&mut a, 0, i as f32, 0.0)).collect();
    frames(&mut a, 3, 0.0);
    a.world.entities[hs[4]].team = Some(1);
    frames(&mut a, 3, 0.05);
    let tail: Vec<usize> = a.world.drawn.iter().rev().take(3).map(|d| d.uploads).collect();
    assert_eq!(tail, [0, 0, 1]);
}

#[test]
fn cloud_dims_the_sun_through_the_light_system() {
    let mut a = app();
    let s = sun(&mut a);
    a.world.cloud = 0.5;
    frames(&mut a, 3, 30.0);
    let t = 30.0 + 2.0 / 60.0;
    let want = CLEAR_SKY_LUX * (1.0 - 0.35) * daylight(t);
    let got = a.world.drawn.last().unwrap().sun_illuminance[s].unwrap();
    assert!((got - want).abs() < 1.0, "sun {got}, want {want}");
}

#[test]
fn the_sun_follows_the_time_of_day_under_cloud() {
    let mut a = app();
    let s = sun(&mut a);
    a.world.cloud = 1.0;
    for t in [0.0, 100.0, 300.0] {
        a.update(t);
        let want = CLEAR_SKY_LUX * 0.3 * daylight(t);
        let got = a.world.drawn.last().unwrap().sun_illuminance[s].unwrap();
        assert!((got - want).abs() < 1.0, "t {t}: sun {got}, want {want}");
    }
}

#[test]
fn cloud_out_of_range_is_clamped() {
    let mut a = app();
    let s = sun(&mut a);
    a.world.cloud = 1.6;
    a.update(0.0);
    let got = a.world.drawn.last().unwrap().sun_illuminance[s].unwrap();
    assert!((got - CLEAR_SKY_LUX * 0.3 * daylight(0.0)).abs() < 1.0, "{got}");
}

#[test]
fn hulls_are_drawn_riding_the_waves() {
    let mut a = app();
    let h = hull(&mut a, 0, 3.0, 2.0);
    for t in [0.25, 0.5, 1.5, 7.75] {
        a.update(t);
        let y = a.world.drawn.last().unwrap().transforms[h].unwrap().y;
        let want = 2.0 * (t * std::f64::consts::PI).sin() as f32;
        assert!((y - want).abs() < 1e-4, "t {t}: drawn y {y}, want {want}");
    }
}

#[test]
fn the_heave_never_reaches_the_simulated_position() {
    let mut a = app();
    let h = hull(&mut a, 0, 3.0, 2.0);
    frames(&mut a, 200, 0.0);
    assert_eq!(a.world.entities[h].sim, Some(Vec3 { x: 3.0, y: 0.0, z: 0.0 }));
    let y = a.world.drawn.last().unwrap().transforms[h].unwrap().y;
    let t = 199.0 / 60.0;
    assert!((y - 2.0 * (t * std::f64::consts::PI).sin() as f32).abs() < 1e-4, "the offset accumulated: {y}");
}

#[test]
fn a_hull_without_heave_sits_on_its_simulated_position() {
    let mut a = app();
    let h = hull(&mut a, 1, -4.0, 0.0);
    a.world.entities[h].heave = None;
    frames(&mut a, 5, 0.3);
    assert_eq!(a.world.drawn.last().unwrap().transforms[h], Some(Vec3 { x: -4.0, y: 0.0, z: 0.0 }));
}
