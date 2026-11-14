use bayer::dither::{bayer, dither_level, threshold};

const B4: [u32; 16] = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
const B8: [u32; 64] = [
    0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26, 12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54,
    22, 3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25, 15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29,
    53, 21,
];

#[test]
fn bayer_2() {
    assert_eq!(bayer(2), vec![0, 2, 3, 1]);
}

#[test]
fn bayer_4() {
    assert_eq!(bayer(4), B4.to_vec());
}

#[test]
fn bayer_8() {
    assert_eq!(bayer(8), B8.to_vec());
}

#[test]
fn each_matrix_holds_every_index_once() {
    for n in [2usize, 4, 8] {
        let mut m = bayer(n);
        m.sort();
        assert_eq!(m, (0..(n * n) as u32).collect::<Vec<_>>(), "bayer({n})");
    }
}

#[test]
#[should_panic]
fn other_sizes_panic() {
    bayer(3);
}

#[test]
fn thresholds_are_centred_in_their_step() {
    assert_eq!(threshold(2, 0, 0), 0.125);
    assert_eq!(threshold(2, 1, 0), 0.625);
    assert_eq!(threshold(4, 3, 3), 5.5 / 16.0);
}

#[test]
fn the_matrix_tiles_negative_coordinates() {
    for n in [2usize, 4, 8] {
        let k = n as i32;
        for (x, y) in [(-1, 0), (0, -1), (-1, -1), (-k, 3), (-k - 1, -2 * k + 1), (-37, -101)] {
            let want = threshold(n, x.rem_euclid(k), y.rem_euclid(k));
            assert_eq!(threshold(n, x, y), want, "n {n} at ({x}, {y})");
        }
    }
}

#[test]
fn a_flat_value_mixes_two_levels_in_proportion() {
    for n in [4usize, 8] {
        for (value, levels) in [(0.25f32, 2u32), (0.5, 2), (0.3, 5), (0.875, 3)] {
            let v = value * (levels - 1) as f32;
            let lo = v.floor() as u32;
            let mut up = 0;
            for y in 0..n as i32 {
                for x in 0..n as i32 {
                    let l = dither_level(value, levels, n, x, y);
                    assert!(l == lo || l == lo + 1, "level {l} for {value}");
                    up += (l == lo + 1) as usize;
                }
            }
            let want = ((v - v.floor()) * (n * n) as f32).round() as usize;
            assert_eq!(up, want, "n {n} value {value} levels {levels}");
        }
    }
}

#[test]
fn extremes_and_out_of_range_values_clamp() {
    for (x, y) in [(0, 0), (3, 1), (-5, 7)] {
        assert_eq!(dither_level(0.0, 4, 4, x, y), 0);
        assert_eq!(dither_level(1.0, 4, 4, x, y), 3);
        assert_eq!(dither_level(-0.2, 4, 4, x, y), 0);
        assert_eq!(dither_level(1.7, 4, 4, x, y), 3);
    }
}

#[test]
fn a_fraction_equal_to_the_threshold_rounds_up() {
    // v = 0.125 at (0, 0) of the 2x2 matrix: the threshold there is (0 + 0.5) / 4
    assert_eq!(dither_level(0.125, 2, 2, 0, 0), 1);
    assert_eq!(dither_level(0.124, 2, 2, 0, 0), 0);
}
