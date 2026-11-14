//! Three CarrierDominion client systems (bj-engine's ultra tier) on the ECS stand-in in `ecs.rs`. Each had a bug that
//! every unit test passed and the screen showed:
//!
//! - `tint_by_team`: every entity with a team and a material shows its team's colour (`TEAM_COLORS[team % 2]`). The
//!   materials are GPU assets: a material that changes is uploaded again, so one that already has the right colour must
//!   not be touched, or every material is re-uploaded every frame.
//! - `weather_dims_sun`: cloud cover dims the sun: its lighting input should be
//!   `CLEAR_SKY_LUX * (1 - 0.7 * cloud)` (cloud clamped to [0, 1]). The engine's `light_system` owns the sun's
//!   illuminance and recomputes it every frame from the sun's `LightBase` and the time of day.
//! - `bob_offset`: hulls ride the waves: each entity with a heave amplitude `a` is drawn `a * sin(time * 2π * 0.5)`
//!   metres above its simulated position, every frame. The simulated position is the server's and is never changed.
//!
//! `register` adds the three systems to the app's Update stage. Make the screen right.
use crate::ecs::{App, Stage, World};

pub const CLEAR_SKY_LUX: f32 = 100_000.0;
pub const TEAM_COLORS: [[f32; 3]; 2] = [[0.2, 0.4, 1.0], [1.0, 0.3, 0.2]];

pub fn register(app: &mut App) {
    app.add_system("tint_by_team", Stage::Update, tint_by_team);
    app.add_system("weather_dims_sun", Stage::Update, weather_dims_sun);
    app.add_system("bob_offset", Stage::Update, bob_offset);
}

pub fn tint_by_team(w: &mut World) {
    for i in 0..w.entities.len() {
        let (Some(team), Some(h)) = (w.entities[i].team, w.entities[i].material) else { continue };
        w.materials.get_mut(h).color = TEAM_COLORS[team as usize % 2];
    }
}

pub fn weather_dims_sun(w: &mut World) {
    let lux = CLEAR_SKY_LUX * (1.0 - 0.7 * w.cloud);
    for e in &mut w.entities {
        if let Some(sun) = e.sun.as_mut() {
            sun.illuminance = lux;
        }
    }
}

pub fn bob_offset(w: &mut World) {
    let phase = (w.time * 2.0 * std::f64::consts::PI * 0.5).sin() as f32;
    for e in &mut w.entities {
        if let (Some(a), Some(t)) = (e.heave, e.transform.as_mut()) {
            t.y += a * phase;
        }
    }
}
