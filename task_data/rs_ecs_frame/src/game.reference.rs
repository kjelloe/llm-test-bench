//! Reference.
use crate::ecs::{App, LightBase, Stage, World};

pub const CLEAR_SKY_LUX: f32 = 100_000.0;
pub const TEAM_COLORS: [[f32; 3]; 2] = [[0.2, 0.4, 1.0], [1.0, 0.3, 0.2]];

pub fn register(app: &mut App) {
    app.add_system("tint_by_team", Stage::Update, tint_by_team);
    app.add_system("weather_dims_sun", Stage::Update, weather_dims_sun);
    app.add_system("bob_offset", Stage::Update, bob_offset).after("sync_transforms");
}

pub fn tint_by_team(w: &mut World) {
    for i in 0..w.entities.len() {
        let (Some(team), Some(h)) = (w.entities[i].team, w.entities[i].material) else { continue };
        let want = TEAM_COLORS[team as usize % 2];
        if w.materials.get(h).color != want {
            w.materials.get_mut(h).color = want;
        }
    }
}

pub fn weather_dims_sun(w: &mut World) {
    let lux = CLEAR_SKY_LUX * (1.0 - 0.7 * w.cloud.clamp(0.0, 1.0));
    for e in &mut w.entities {
        if e.sun.is_some() {
            e.light_base = Some(LightBase { lux });
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
