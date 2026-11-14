//! The canvas's own conversion (read-only for this task): premultiplied RGBA8, the canvas's storage, to straight-alpha
//! RGBA8, what `getImageData` returns. Per channel `(c / (a / 255) + 0.5)` truncated, in f64; alpha unchanged; a pixel
//! with alpha 255 is returned as it is. Stored pixels are always valid premultiplied colour: r, g, b <= a.
pub fn demultiply_pixel(p: [u8; 4]) -> [u8; 4] {
    let a = p[3];
    if a == 255 {
        return p;
    }
    let af = a as f64 / 255.0;
    let div = |c: u8| (c as f64 / af + 0.5) as u8;
    [div(p[0]), div(p[1]), div(p[2]), a]
}

pub fn demultiply_slow(src: &[u8], dst: &mut [u8]) {
    for (s, d) in src.chunks_exact(4).zip(dst.chunks_exact_mut(4)) {
        d.copy_from_slice(&demultiply_pixel([s[0], s[1], s[2], s[3]]));
    }
}
