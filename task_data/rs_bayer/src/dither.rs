//! Ordered (Bayer) dithering for the pixel-art styles (bj-engine's `procgen::bayer` and the dither pass). The GPU pass
//! and this CPU twin must agree pixel for pixel.
//!
//! - `bayer(n)` for n in {2, 4, 8}: the n×n Bayer index matrix, row-major, values 0..n²-1. It is built recursively:
//!   bayer(1) = [0]; each entry v of bayer(n/2) becomes the 2×2 block [[4v, 4v+2], [4v+3, 4v+1]], placed at the same
//!   position in each of the four n/2 × n/2 quadrants: top-left gets 4v, top-right 4v+2, bottom-left 4v+3, bottom-right
//!   4v+1. So bayer(2) = [0, 2, 3, 1]. Other n panic.
//! - `threshold(n, x, y)`: the matrix tiled over the whole plane (negative coordinates too), as
//!   `(index + 0.5) / n²`.
//! - `dither_level(value, levels, n, x, y)`: quantise value (clamped to [0, 1]) to one of `levels` (>= 2) levels:
//!   `v = value * (levels - 1)`; the level is `floor(v) + 1` when the fractional part of v is at least the threshold,
//!   else `floor(v)`; never above `levels - 1`.
//!
//! The first version had the matrix digits reversed, and only a GPU-versus-CPU comparison found it.
pub fn bayer(n: usize) -> Vec<u32> {
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
                out[y * size + x + half] = base + 1;
                out[(y + half) * size + x] = base + 3;
                out[(y + half) * size + x + half] = base + 2;
            }
        }
        out
    }
    build(n)
}

pub fn threshold(n: usize, x: i32, y: i32) -> f32 {
    let m = bayer(n);
    let (tx, ty) = ((x % n as i32) as usize, (y % n as i32) as usize);
    m[ty * n + tx] as f32 / (n * n) as f32
}

pub fn dither_level(value: f32, levels: u32, n: usize, x: i32, y: i32) -> u32 {
    let v = value * (levels - 1) as f32;
    let base = v.floor();
    if v - base > threshold(n, x, y) {
        base as u32 + 1
    } else {
        base as u32
    }
}
