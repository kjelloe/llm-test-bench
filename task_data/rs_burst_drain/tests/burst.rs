//! Frames from a captured CarrierDominion run at ×16 (fixtures/, see tools/make_fixtures.reference.py).
use burst_drain::burst::drain;
use burst_drain::json::Value;
use burst_drain::wire;

fn frame(name: &str) -> String {
    std::fs::read_to_string(format!("{}/fixtures/{name}.json", env!("CARGO_MANIFEST_DIR"))).unwrap()
}
fn run(i: usize) -> String {
    frame(&format!("run_{i:02}"))
}
fn tagged(texts: &[&str]) -> Vec<(i64, Value)> {
    let mut want = Vec::new();
    for t in texts {
        if wire::kind(t) == Some("snapshot") {
            if let Ok((tick, events)) = wire::read_events(t) {
                want.extend(events.into_iter().map(|e| (tick, e)));
            }
        }
    }
    want
}

#[test]
fn a_burst_of_16_keeps_every_event_in_order() {
    let frames: Vec<String> = (0..16).map(run).collect();
    let texts: Vec<&str> = frames.iter().map(String::as_str).collect();
    let d = drain(&texts);
    let want = tagged(&texts);
    assert_eq!(want.len(), 7, "fixture check");
    assert_eq!(d.events, want);
    assert_eq!(d.snapshots, 16);
    assert!(d.bad.is_empty() && d.others.is_empty());
}

#[test]
fn the_newest_snapshot_is_the_one_drawn() {
    let frames: Vec<String> = (0..16).map(run).collect();
    let texts: Vec<&str> = frames.iter().map(String::as_str).collect();
    let d = drain(&texts);
    assert_eq!(d.newest, Some(wire::decode_snapshot(&frames[15]).unwrap()));
}

#[test]
fn only_one_full_decode_per_frame() {
    let frames: Vec<String> = (0..16).map(run).collect();
    let texts: Vec<&str> = frames.iter().map(String::as_str).collect();
    let before = wire::full_decodes();
    drain(&texts);
    assert_eq!(wire::full_decodes() - before, 1, "decode_snapshot is the expensive call");
}

#[test]
fn other_messages_pass_through_in_arrival_order() {
    let (a, b, c, d) = (run(0), frame("lobby"), run(1), frame("spectatorSnapshot"));
    let w = frame("lobbyWelcome");
    let out = drain(&[&w, &a, &b, &c, &d]);
    let kinds: Vec<&str> = out.others.iter().map(|m| m.kind.as_str()).collect();
    assert_eq!(kinds, ["welcome", "lobby"]);
    assert_eq!(out.newest.as_ref().map(|s| s.tick), Some(3392), "the spectator snapshot came last");
    assert_eq!(out.snapshots, 3);
}

#[test]
fn a_welcome_ends_the_old_session_view_but_keeps_its_events() {
    let (early, w, late) = (run(2), frame("welcome"), run(7));
    let d = drain(&[&early, &w, &late]);
    assert_eq!(d.newest.as_ref().map(|s| s.tick), Some(3400));
    assert_eq!(d.events, tagged(&[&early, &late]));
    assert_eq!(d.events.iter().filter(|e| e.0 == 3395).count(), 2);
}

#[test]
fn snapshots_before_the_last_welcome_are_never_drawn() {
    let (s, w) = (run(7), frame("welcome"));
    let d = drain(&[&s, &w]);
    assert!(d.newest.is_none(), "the only snapshot belongs to the old session");
    assert_eq!(d.events, tagged(&[&s]));
    assert_eq!(d.others.len(), 1);
}

#[test]
fn a_broken_newest_snapshot_falls_back_to_the_one_before() {
    let (a, b, broken) = (run(5), run(6), frame("broken"));
    let before = wire::full_decodes();
    let d = drain(&[&a, &b, &broken]);
    assert_eq!(d.newest.as_ref().map(|s| s.tick), Some(3399));
    assert_eq!(d.bad.iter().map(|b| b.0).collect::<Vec<_>>(), [2], "reported once");
    assert!(wire::full_decodes() - before <= 2);
}

#[test]
fn a_bad_frame_does_not_stop_the_rest() {
    let (a, b, l) = (run(0), run(7), frame("lobby"));
    let d = drain(&[&a, "not json", &b, &l]);
    assert_eq!(d.bad.iter().map(|b| b.0).collect::<Vec<_>>(), [1]);
    assert_eq!(d.events, tagged(&[&b]));
    assert_eq!(d.newest.as_ref().map(|s| s.tick), Some(3400));
    assert_eq!(d.others.len(), 1);
    assert_eq!(d.snapshots, 2);
}

#[test]
fn a_frame_without_snapshots() {
    let (w, l) = (frame("lobbyWelcome"), frame("lobby"));
    let d = drain(&[&w, &l]);
    assert!(d.newest.is_none() && d.events.is_empty() && d.bad.is_empty());
    assert_eq!((d.others.len(), d.snapshots), (2, 0));
}

#[test]
fn a_broken_snapshot_in_the_middle_of_a_burst() {
    let (a, broken, b) = (run(5), frame("broken"), run(7));
    let d = drain(&[&a, &broken, &b]);
    assert_eq!(d.bad.iter().map(|b| b.0).collect::<Vec<_>>(), [1]);
    assert_eq!(d.events, tagged(&[&a, &b]));
    assert_eq!(d.newest.as_ref().map(|s| s.tick), Some(3400));
    assert_eq!(d.snapshots, 2);
}
