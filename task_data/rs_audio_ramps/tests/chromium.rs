//! Every case's samples were rendered by headless Chromium (tools/make_fixtures.reference.mjs): a ConstantSourceNode
//! whose offset (default 1) gets the case's automation calls, in an OfflineAudioContext at 48 kHz.
use audio_ramps::param::Param;

fn fixture(name: &str) -> String {
    std::fs::read_to_string(format!("{}/fixtures/{name}.txt", env!("CARGO_MANIFEST_DIR"))).unwrap()
}

fn check(case: &str) {
    let cases = fixture("cases");
    let line = cases.lines().find(|l| l.split('|').next() == Some(case)).expect("case");
    let mut p = Param::new(1.0);
    for ev in line.split('|').skip(1) {
        let f: Vec<&str> = ev.split(' ').collect();
        let n = |i: usize| f[i].parse::<f64>().unwrap();
        match f[0] {
            "setValueAtTime" => p.set_value_at_time(n(1) as f32, n(2)),
            "linearRampToValueAtTime" => p.linear_ramp_to_value_at_time(n(1) as f32, n(2)),
            "exponentialRampToValueAtTime" => p.exponential_ramp_to_value_at_time(n(1) as f32, n(2)),
            "setTargetAtTime" => p.set_target_at_time(n(1) as f32, n(2), n(3)),
            other => panic!("{other}"),
        }
    }
    let want: Vec<f32> = fixture(case).lines().map(|l| l.parse().unwrap()).collect();
    let got = p.render(48000.0, want.len());
    let mut worst = (0usize, 0.0f32);
    for (i, (&g, &w)) in got.iter().zip(&want).enumerate() {
        let err = if g.is_nan() { f32::INFINITY } else { (g - w).abs() };
        if err > worst.1 {
            worst = (i, err);
        }
    }
    let i = worst.0;
    assert!(worst.1 <= 1e-4, "{case}: sample {i} (t = {:.6} s) is {}, Chromium gives {}", i as f64 / 48000.0, got[i], want[i]);
}

macro_rules! cases {
    ($($name:ident),*) => { $( #[test] fn $name() { check(stringify!($name)); } )* };
}

cases!(
    default_only, set_value, linear_ramp, exponential_decay, exponential_from_zero, exponential_opposite_signs,
    ramp_without_earlier_event, exponential_without_earlier_event, set_target, set_target_then_set_value,
    same_time_later_wins, ramp_ends_between_samples, chained, value_after_ramp, out_of_order_calls, target_after_target,
    ramp_after_target
);
