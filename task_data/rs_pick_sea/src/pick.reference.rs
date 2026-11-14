//! Reference (bj-engine's carrierdominion_game::pick).
pub type V3 = [f64; 3];

fn sub(a: V3, b: V3) -> V3 {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}
fn cross(a: V3, b: V3) -> V3 {
    [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
}
fn normal(a: V3) -> V3 {
    let l = (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]).sqrt();
    [a[0] / l, a[1] / l, a[2] / l]
}

pub fn js_round(x: f64) -> f64 {
    (x + 0.5).floor()
}

#[derive(Debug, Clone, Copy)]
pub struct Camera {
    pub eye: V3,
    pub target: V3,
    pub fov_degrees: f64,
    pub aspect: f64,
}

pub fn pick_sea(camera: &Camera, ndc_x: f64, ndc_y: f64) -> Option<(i64, i64)> {
    let z = normal(sub(camera.eye, camera.target));
    let x = normal(cross([0.0, 1.0, 0.0], z));
    let y = cross(z, x);
    let tan = (camera.fov_degrees.to_radians() / 2.0).tan();
    let (cx, cy) = (ndc_x * tan * camera.aspect, ndc_y * tan);
    let d = normal([cx * x[0] + cy * y[0] - z[0], cx * x[1] + cy * y[1] - z[1], cx * x[2] + cy * y[2] - z[2]]);
    if d[1] == 0.0 {
        return None;
    }
    let along = -camera.eye[1] / d[1];
    if along < 0.0 {
        return None;
    }
    let (px, pz) = (camera.eye[0] + d[0] * along, camera.eye[2] + d[2] * along);
    Some((js_round(px * 256.0) as i64, js_round(-pz * 256.0) as i64))
}
