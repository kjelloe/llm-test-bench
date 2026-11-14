//! `render/scene.js pickSea` for the native CarrierDominion client: a click on the window to the point on the sea it
//! means, in engine units. The browser does it with three.js: a PerspectiveCamera (vertical field of view `fov_degrees`,
//! viewport `aspect` = width / height) placed at `eye` and turned with `lookAt(target)` (up is +y), then
//! `Raycaster.setFromCamera(ndc, camera)` (ndc: x right, y up, both -1..1 across the viewport) and the ray's
//! intersection with the sea, the plane y = 0. A ray along the plane or pointing away from it misses (None).
//!
//! Scene axes are three's: x east, y up, z south. Engine units are 256 per metre with y north, so the hit is
//! `(Math.round(x * 256), Math.round(-z * 256))`; `js_round` is JavaScript's `Math.round` (halves go up, for negative
//! numbers too). The tests replay picks captured from the browser.
//!
//! This first version was written from memory of the maths.
pub type V3 = [f64; 3];

/// JavaScript's `Math.round`.
pub fn js_round(x: f64) -> f64 {
    x.round()
}

#[derive(Debug, Clone, Copy)]
pub struct Camera {
    pub eye: V3,
    pub target: V3,
    pub fov_degrees: f64,
    pub aspect: f64,
}

pub fn pick_sea(camera: &Camera, ndc_x: f64, ndc_y: f64) -> Option<(i64, i64)> {
    let f = [camera.target[0] - camera.eye[0], camera.target[1] - camera.eye[1], camera.target[2] - camera.eye[2]];
    let fl = (f[0] * f[0] + f[1] * f[1] + f[2] * f[2]).sqrt();
    let f = [f[0] / fl, f[1] / fl, f[2] / fl];
    let r = [f[2], 0.0, -f[0]];
    let u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]];
    let tan = (camera.fov_degrees.to_radians() / 2.0).tan();
    let (cx, cy) = (ndc_x * tan, ndc_y * tan);
    let d = [f[0] + cx * r[0] + cy * u[0], f[1] + cx * r[1] + cy * u[1], f[2] + cx * r[2] + cy * u[2]];
    if d[1] == 0.0 {
        return None;
    }
    let along = -camera.eye[1] / d[1];
    let (px, pz) = (camera.eye[0] + d[0] * along, camera.eye[2] + d[2] * along);
    Some((js_round(px * 256.0) as i64, js_round(pz * 256.0) as i64))
}
