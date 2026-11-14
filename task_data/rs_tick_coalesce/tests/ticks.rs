use tick_coalesce::ticks::TickClock;

fn run(frames: &[f64]) -> Vec<u32> {
    let mut c = TickClock::new(50.0);
    frames.iter().map(|&t| c.frame(t)).collect()
}

#[test]
fn first_frame_emits_nothing() {
    assert_eq!(run(&[1000.0]), vec![0]);
}

#[test]
fn steady_60fps_ticks_every_third_frame() {
    let frames: Vec<f64> = (0..31).map(|i| i as f64 * 1000.0 / 60.0).collect();
    let ticks = run(&frames);
    assert_eq!(ticks.iter().sum::<u32>(), 10, "500 ms at 60 fps holds 10 ticks");
    assert!(ticks.iter().all(|&n| n <= 1));
}

#[test]
fn a_grid_point_exactly_at_the_frame_counts() {
    assert_eq!(run(&[0.0, 50.0, 100.0, 149.0, 150.0]), vec![0, 1, 1, 0, 1]);
}

#[test]
fn a_hitch_emits_one_tick_not_a_burst() {
    assert_eq!(run(&[0.0, 260.0]), vec![0, 1]);
}

#[test]
fn missed_beats_are_dropped_not_spread_over_later_frames() {
    // after a 260 ms hitch the next grid point is 300; frames at 270, 280, 290 must not tick
    assert_eq!(run(&[0.0, 260.0, 270.0, 280.0, 290.0, 300.0]), vec![0, 1, 0, 0, 0, 1]);
}

#[test]
fn the_next_tick_stays_on_the_grid_after_a_late_frame() {
    // a late frame at 70 ticks; the next is due at 100, not at 120
    assert_eq!(run(&[0.0, 70.0, 100.0, 119.0, 120.0, 150.0]), vec![0, 1, 1, 0, 0, 1]);
}

#[test]
fn frames_with_the_same_time_tick_once() {
    assert_eq!(run(&[0.0, 50.0, 50.0, 50.0]), vec![0, 1, 0, 0]);
}

#[test]
fn slow_frames_tick_once_each() {
    // 20 fps rendering at 75 ms per frame: every frame passes a grid point
    let frames: Vec<f64> = (0..9).map(|i| i as f64 * 75.0).collect();
    assert_eq!(run(&frames), vec![0, 1, 1, 1, 1, 1, 1, 1, 1]);
}

#[test]
fn nothing_ticks_while_paused() {
    let mut c = TickClock::new(50.0);
    assert_eq!(c.frame(0.0), 0);
    assert_eq!(c.frame(50.0), 1);
    c.pause();
    assert_eq!([c.frame(100.0), c.frame(400.0), c.frame(900.0)], [0, 0, 0]);
}

#[test]
fn resume_starts_a_fresh_grid() {
    let mut c = TickClock::new(50.0);
    c.frame(0.0);
    c.frame(50.0);
    c.pause();
    c.frame(1000.0);
    c.resume(1010.0);
    // the new grid starts at 1010: due at 1060, 1110; the frame at 1050 is before it
    assert_eq!([c.frame(1020.0), c.frame(1050.0), c.frame(1060.0), c.frame(1100.0), c.frame(1110.0)], [0, 0, 1, 0, 1]);
}

#[test]
fn an_hour_at_144fps_keeps_the_tick_count() {
    let mut c = TickClock::new(50.0);
    let mut n = 0u64;
    let frames = 144 * 3600;
    for i in 0..=frames {
        n += c.frame(i as f64 * 1000.0 / 144.0) as u64;
    }
    assert_eq!(n, 72_000);
}
