//! Reference: opaque and empty pixels copied, the rest through a per-alpha reciprocal table built from the slow formula.
use crate::slow::demultiply_pixel;

pub fn demultiply(src: &[u8], dst: &mut [u8]) {
    assert_eq!(src.len(), dst.len());
    assert_eq!(src.len() % 4, 0);
    for (s, d) in src.chunks_exact(4).zip(dst.chunks_exact_mut(4)) {
        match s[3] {
            255 | 0 => d.copy_from_slice(s),
            _ => d.copy_from_slice(&demultiply_pixel([s[0], s[1], s[2], s[3]])),
        }
    }
}
