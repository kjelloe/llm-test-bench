//! Reference.
pub fn bayer(n: usize) -> Vec<u32> {
    assert!(matches!(n, 2 | 4 | 8), "bayer({n})");
    fn build(size: usize) -> Vec<u32> {
        if size == 1 {
            return vec![0];
        }
        let half = size / 2;
        let prev = build(half);
        let mut out = vec![0; size * size];
        for y in 0..half {
            for x in 0..half {
                let base = prev[y * half + x] * 4;
                out[y * size + x] = base;
                out[y * size + x + half] = base + 2;
                out[(y + half) * size + x] = base + 3;
                out[(y + half) * size + x + half] = base + 1;
            }
        }
        out
    }
    build(n)
}

pub fn threshold(n: usize, x: i32, y: i32) -> f32 {
    let m = bayer(n);
    let (tx, ty) = (x.rem_euclid(n as i32) as usize, y.rem_euclid(n as i32) as usize);
    (m[ty * n + tx] as f32 + 0.5) / (n * n) as f32
}

pub fn dither_level(value: f32, levels: u32, n: usize, x: i32, y: i32) -> u32 {
    assert!(levels >= 2);
    let v = value.clamp(0.0, 1.0) * (levels - 1) as f32;
    let base = v.floor();
    let level = if v - base >= threshold(n, x, y) { base as u32 + 1 } else { base as u32 };
    level.min(levels - 1)
}
