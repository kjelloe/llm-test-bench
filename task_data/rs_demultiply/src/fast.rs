//! `demultiply` converts a whole canvas from premultiplied to straight alpha and is a measured hotspot: the HUD reads
//! its canvases back every frame. Make it fast without changing a single output byte: it must give exactly what
//! `slow::demultiply_slow` gives, for every valid premultiplied pixel (r, g, b <= a). Most of a HUD canvas is fully
//! opaque or fully empty. `src` and `dst` have the same length, a multiple of 4; panic otherwise.
//!
//! This first attempt uses integer arithmetic to avoid the division in floating point.
pub fn demultiply(src: &[u8], dst: &mut [u8]) {
    for (s, d) in src.chunks_exact(4).zip(dst.chunks_exact_mut(4)) {
        let a = s[3] as u32;
        if a == 0 {
            d.copy_from_slice(&[0, 0, 0, 0]);
            continue;
        }
        for c in 0..3 {
            d[c] = ((s[c] as u32 * 255 + a / 2) / a).min(255) as u8;
        }
        d[3] = s[3];
    }
}
