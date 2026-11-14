use demultiply::fast::demultiply;
use demultiply::slow::demultiply_slow;
use std::time::Instant;

/// Every valid premultiplied (value, alpha) pair, in all three colour channels.
fn every_pair() -> Vec<u8> {
    let mut v = Vec::new();
    for a in 0..=255u8 {
        for c in 0..=a {
            v.extend_from_slice(&[c, a - c / 2, c / 3, a]);
            v.extend_from_slice(&[a - c, c, a, a]);
        }
    }
    v
}

fn compare(src: &[u8]) {
    let (mut want, mut got) = (vec![7u8; src.len()], vec![9u8; src.len()]);
    demultiply_slow(src, &mut want);
    demultiply(src, &mut got);
    let first = (0..src.len() / 4).find(|&i| want[i * 4..i * 4 + 4] != got[i * 4..i * 4 + 4]);
    if let Some(i) = first {
        panic!("pixel {:?} gives {:?}, the canvas gives {:?}", &src[i * 4..i * 4 + 4], &got[i * 4..i * 4 + 4], &want[i * 4..i * 4 + 4]);
    }
}

/// A HUD-like canvas: 95% fully opaque or fully empty, the rest anti-aliased edges and translucent panels.
fn hud(w: usize, h: usize) -> Vec<u8> {
    let mut s: u32 = 0x2545_f491;
    let mut rnd = move || {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        s
    };
    let mut v = Vec::with_capacity(w * h * 4);
    for _ in 0..w * h {
        let r = rnd();
        let a = match r % 20 {
            0..=11 => 0u8,
            12..=18 => 255,
            _ => (r >> 8) as u8,
        };
        let c = |shift: u32| (((r >> shift) & 0xff) as u16 % (a as u16 + 1)) as u8;
        v.extend_from_slice(&[c(4), c(12), c(20), a]);
    }
    v
}

#[test]
fn every_translucent_value_matches_the_canvas() {
    compare(&every_pair());
}

#[test]
fn opaque_pixels_are_unchanged() {
    let src: Vec<u8> = (0..=255u8).flat_map(|v| [v, 255 - v, v / 2, 255]).collect();
    compare(&src);
}

#[test]
fn empty_pixels_stay_empty() {
    compare(&[0, 0, 0, 0, 0, 0, 0, 0]);
}

#[test]
fn a_hud_canvas_matches_byte_for_byte() {
    compare(&hud(512, 256));
}

#[test]
fn an_empty_input_is_fine() {
    let mut d: [u8; 0] = [];
    demultiply(&[], &mut d);
}

#[test]
#[should_panic]
fn mismatched_lengths_panic() {
    let mut d = [0u8; 4];
    demultiply(&[1, 1, 1, 1, 2, 2, 2, 2], &mut d);
}

#[test]
fn a_hud_canvas_converts_at_least_twice_as_fast() {
    let src = hud(1024, 1024);
    let mut dst = vec![0u8; src.len()];
    let time = |f: &dyn Fn(&[u8], &mut [u8]), dst: &mut Vec<u8>| {
        (0..7)
            .map(|_| {
                let t = Instant::now();
                f(&src, dst);
                std::hint::black_box(&dst);
                t.elapsed().as_secs_f64()
            })
            .fold(f64::INFINITY, f64::min)
    };
    let slow = time(&demultiply_slow, &mut dst);
    let fast = time(&demultiply, &mut dst);
    assert!(fast * 2.0 <= slow, "fast {:.2} ms vs the canvas's {:.2} ms", fast * 1e3, slow * 1e3);
}
