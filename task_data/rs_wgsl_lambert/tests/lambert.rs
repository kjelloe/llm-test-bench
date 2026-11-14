//! Each case's pixel must be what three r162 draws for a MeshLambertMaterial under its lights (NoToneMapping, sRGB
//! output): colours decoded from sRGB, irradiance = ambient + hemisphere mix(ground, sky, n.y / 2 + 1/2) + the sum of
//! colour * intensity * max(dot(n, L), 0), diffuse = irradiance * albedo / pi, then sRGB-encoded; ±1 per channel.
use wgsl_lambert::{render, Case, Sun};

fn hex(h: u32) -> [f32; 3] {
    [((h >> 16) & 255) as f32 / 255.0, ((h >> 8) & 255) as f32 / 255.0, (h & 255) as f32 / 255.0]
}
fn lin(c: f64) -> f64 {
    if c < 0.04045 { c * 0.0773993808 } else { (c * 0.9478672986 + 0.0521327014).powf(2.4) }
}
fn srgb(c: f64) -> f64 {
    if c <= 0.0031308 { c * 12.92 } else { 1.055 * c.powf(1.0 / 2.4) - 0.055 }
}
fn unit(v: [f64; 3]) -> [f64; 3] {
    let n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt();
    [v[0] / n, v[1] / n, v[2] / n]
}

fn three(c: &Case) -> [u8; 3] {
    let n = unit(c.normal.map(f64::from));
    let mut irr = [0.0f64; 3];
    for k in 0..3 {
        irr[k] += lin(c.ambient.0[k] as f64) * c.ambient.1 as f64;
        if let Some((sky, ground, i)) = c.hemisphere {
            let w = n[1] * 0.5 + 0.5;
            let (s, g) = (lin(sky[k] as f64) * i as f64, lin(ground[k] as f64) * i as f64);
            irr[k] += g + (s - g) * w;
        }
    }
    for s in &c.suns {
        let l = unit([0, 1, 2].map(|k| (s.position[k] - s.target[k]) as f64));
        let d = (n[0] * l[0] + n[1] * l[1] + n[2] * l[2]).max(0.0);
        for k in 0..3 {
            irr[k] += lin(s.color[k] as f64) * s.intensity as f64 * d;
        }
    }
    [0, 1, 2].map(|k| (255.0 * srgb((irr[k] * lin(c.material[k] as f64) / std::f64::consts::PI).clamp(0.0, 1.0))).round() as u8)
}

fn sun(h: u32, intensity: f32, position: [f32; 3], target: [f32; 3]) -> Sun {
    Sun { color: hex(h), intensity, position, target }
}
fn case(material: u32, normal: [f32; 3], ambient: (u32, f32), hemi: Option<(u32, u32, f32)>, suns: Vec<Sun>) -> Case {
    Case { material: hex(material), normal, ambient: (hex(ambient.0), ambient.1), hemisphere: hemi.map(|(s, g, i)| (hex(s), hex(g), i)), suns }
}

fn cases() -> Vec<(&'static str, Case)> {
    let up = [0.0, 1.0, 0.0];
    vec![
        ("ambient_only", case(0xcccccc, up, (0xffffff, 2.0), None, vec![])),
        ("ambient_tinted", case(0x88aaff, up, (0xffeedd, 1.5), None, vec![])),
        ("sun_overhead", case(0xbbbbbb, up, (0x000000, 0.0), None, vec![sun(0xffffff, 2.5, [0.0, 10.0, 0.0], [0.0, 0.0, 0.0])])),
        ("sun_slanted", case(0xbbbbbb, up, (0x101010, 1.0), None, vec![sun(0xfff4e0, 3.0, [10.0, 6.0, 4.0], [0.0, 0.0, 0.0])])),
        ("sun_target_off_origin", case(0x99cc66, up, (0x000000, 0.0), None, vec![sun(0xffffff, 3.0, [5.0, 5.0, 5.0], [5.0, 0.0, 0.0])])),
        ("sun_behind_surface", case(0xcccccc, up, (0x404040, 1.0), None, vec![sun(0xffffff, 4.0, [0.0, -10.0, 0.0], [0.0, 0.0, 0.0])])),
        ("two_suns", case(0xaaaaaa, [0.0, 0.0, 1.0], (0x000000, 0.0), None, vec![sun(0xff8844, 2.0, [3.0, 0.0, 4.0], [0.0; 3]), sun(0x4488ff, 1.5, [-4.0, 0.0, 3.0], [0.0; 3])])),
        ("hemi_facing_up", case(0xdddddd, up, (0x000000, 0.0), Some((0x87ceeb, 0x3a2a1a, 2.0)), vec![])),
        ("hemi_facing_down", case(0xdddddd, [0.0, -1.0, 0.0], (0x000000, 0.0), Some((0x87ceeb, 0x3a2a1a, 2.0)), vec![])),
        ("hemi_sideways", case(0xdddddd, [1.0, 0.0, 0.0], (0x000000, 0.0), Some((0x87ceeb, 0x3a2a1a, 2.0)), vec![])),
        ("hemi_tilted", case(0xdddddd, [0.3, 0.8, 0.5], (0x000000, 0.0), Some((0xaaccff, 0x553311, 1.6)), vec![])),
        ("hemi_plus_sun", case(0xc0b090, up, (0x000000, 0.0), Some((0xbfd8ff, 0x2b3a28, 1.2)), vec![sun(0xfff0d0, 2.2, [6.0, 8.0, -2.0], [0.0; 3])])),
        ("carrier_deck", case(0x5a6068, up, (0x6f7f8f, 0.6), Some((0xbcd4ec, 0x1f3a52, 0.9)), vec![sun(0xfff4e6, 2.4, [3000.0, 4200.0, 1800.0], [0.0; 3])])),
        ("carrier_hull_side", case(0x3d4650, [1.0, 0.0, 0.0], (0x6f7f8f, 0.6), Some((0xbcd4ec, 0x1f3a52, 0.9)), vec![sun(0xfff4e6, 2.4, [3000.0, 4200.0, 1800.0], [0.0; 3])])),
        ("dark_material", case(0x202020, up, (0xffffff, 1.0), None, vec![sun(0xffffff, 3.0, [0.0, 1.0, 0.0], [0.0; 3])])),
        ("near_black", case(0x050505, up, (0xffffff, 0.5), None, vec![])),
        ("overexposed_clamps", case(0xffffff, up, (0xffffff, 8.0), None, vec![sun(0xffffff, 10.0, [0.0, 1.0, 0.0], [0.0; 3])])),
        ("dim_red", case(0xff2010, up, (0x000000, 0.0), None, vec![sun(0xffffff, 0.4, [1.0, 2.0, 0.0], [0.0; 3])])),
        ("unnormalised_normal", case(0xbbbbbb, [0.0, 7.5, 0.0], (0x000000, 0.0), None, vec![sun(0xffffff, 2.0, [0.0, 3.0, 4.0], [0.0; 3])])),
        ("four_suns", case(0xa0a0a0, [0.2, 0.9, 0.3], (0x0a0a0a, 1.0), None, vec![
            sun(0xffffff, 1.0, [1.0, 1.0, 0.0], [0.0; 3]), sun(0xff0000, 1.0, [-1.0, 1.0, 0.0], [0.0; 3]),
            sun(0x00ff00, 1.0, [0.0, 1.0, 1.0], [0.0; 3]), sun(0x0000ff, 1.0, [0.0, -1.0, 0.0], [0.0; 3])])),
    ]
}

fn check(name: &str) {
    let all = cases();
    let (_, c) = all.iter().find(|(n, _)| *n == name).unwrap();
    let got = render(std::slice::from_ref(c))[0];
    let want = three(c);
    let off = (0..3).map(|k| (got[k] as i32 - want[k] as i32).abs()).max().unwrap();
    assert!(off <= 1 && got[3] == 255, "{name}: the shader gives {:?}, three draws {:?}", &got[..3], want);
}

macro_rules! cases {
    ($($name:ident),*) => { $( #[test] fn $name() { check(stringify!($name)); } )* };
}

cases!(
    ambient_only, ambient_tinted, sun_overhead, sun_slanted, sun_target_off_origin, sun_behind_surface, two_suns,
    hemi_facing_up, hemi_facing_down, hemi_sideways, hemi_tilted, hemi_plus_sun, carrier_deck, carrier_hull_side,
    dark_material, near_black, overexposed_clamps, dim_red, unnormalised_normal, four_suns
);
