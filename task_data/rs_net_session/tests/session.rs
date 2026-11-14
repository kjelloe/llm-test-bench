use net_session::session::*;

/// Ticks every millisecond from `from` to `to` (seconds); the times at which a dial came out, with the URL.
fn dials(s: &mut Session, from: f64, to: f64) -> Vec<(f64, String)> {
    let mut out = Vec::new();
    for ms in (from * 1000.0).round() as i64..=(to * 1000.0).round() as i64 {
        let t = ms as f64 / 1000.0;
        if let Some(u) = s.tick(t) {
            out.push((t, u));
        }
    }
    out
}

#[test]
fn url_helpers() {
    assert_eq!(with_query("ws://h", "token", "a"), "ws://h/?token=a");
    assert_eq!(with_query("ws://h:1/ws", "token", "a"), "ws://h:1/ws?token=a");
    assert_eq!(with_query("ws://h/?proto=1&token=old&x=2", "token", "new"), "ws://h/?proto=1&x=2&token=new");
    assert_eq!(without_query("wss://h/ws?token=x#y"), "wss://h/ws");
    assert_eq!(without_query("wss://h/ws#frag"), "wss://h/ws");
    assert_eq!(origin("wss://game.example:8443/ws?token=x"), "wss://game.example:8443");
    assert_eq!(origin("ws://h"), "ws://h");
}

#[test]
fn a_dropped_connection_redials_after_one_second() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_open(g);
    s.on_close(g, 1006, 10.0);
    assert_eq!(dials(&mut s, 10.0, 12.0), [(11.0, "ws://h/ws".to_string())]);
}

#[test]
fn failed_attempts_back_off_by_1_7_up_to_5_seconds() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_open(g);
    let mut now = 0.0;
    let mut waits = Vec::new();
    for _ in 0..7 {
        s.on_close(g, 1006, now);
        let d = dials(&mut s, now, now + 6.0);
        assert_eq!(d.len(), 1);
        waits.push(((d[0].0 - now) * 1000.0).round() / 1000.0);
        now = d[0].0;
    }
    let want = [1.0, 1.7, 2.89, 4.913, 5.0, 5.0, 5.0];
    assert!(waits.iter().zip(want).all(|(w, e)| (w - e).abs() <= 0.0015), "waits {waits:?}, want {want:?}");
}

#[test]
fn an_open_resets_the_backoff() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_close(g, 1006, 0.0);
    s.on_close(g, 1006, 1.0);
    s.on_open(g);
    s.on_close(g, 1006, 20.0);
    assert_eq!(dials(&mut s, 20.0, 26.0).first().map(|d| d.0), Some(21.0));
}

#[test]
fn a_kicked_client_forgets_its_token_and_stays_down() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_open(g);
    s.on_welcome(g, Some("T1"), false);
    assert_eq!(s.dial_url(), "ws://h/ws?token=T1");
    s.on_close(g, KICKED, 5.0);
    assert_eq!(s.stopped(), Some("kicked"));
    assert!(dials(&mut s, 5.0, 30.0).is_empty());
    s.connect("ws://h/ws");
    assert_eq!(s.dial_url(), "ws://h/ws", "the token went with the kick");
}

#[test]
fn a_superseded_session_never_resumes_by_itself() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_open(g);
    s.on_welcome(g, Some("T1"), false);
    s.on_close(g, SUPERSEDED, 3.0);
    assert_eq!(s.stopped(), Some("superseded"));
    assert!(dials(&mut s, 3.0, 40.0).is_empty());
    s.on_close(g, 1006, 41.0);
    assert!(dials(&mut s, 41.0, 50.0).is_empty(), "a late close of the old socket must not restart it");
    let g2 = s.connect("ws://h/ws");
    assert!(g2 > g && s.stopped().is_none());
    assert_eq!(s.dial_url(), "ws://h/ws?token=T1", "a manual retake keeps the seat");
}

#[test]
fn a_closed_room_is_final() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_open(g);
    s.on_close(g, ROOM_CLOSED, 1.0);
    assert_eq!(s.stopped(), Some("room closed"));
    assert!(dials(&mut s, 1.0, 20.0).is_empty());
}

#[test]
fn ordinary_close_codes_reconnect() {
    for code in [1000u16, 1001, 1006, 1011, 4002, 4999] {
        let mut s = Session::new("ws://h/ws");
        let g = s.generation();
        s.on_open(g);
        s.on_close(g, code, 0.0);
        assert!(s.stopped().is_none(), "{code}");
        assert_eq!(dials(&mut s, 0.0, 2.0).len(), 1, "{code}");
    }
}

#[test]
fn a_403_is_final_and_a_401_is_retried_once() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_refused(g, 403, 0.0);
    assert_eq!(s.stopped(), Some("refused 403"));

    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_refused(g, 401, 0.0);
    assert!(s.stopped().is_none());
    assert_eq!(dials(&mut s, 0.0, 3.0).iter().map(|d| d.0).collect::<Vec<_>>(), [2.0]);
    s.on_refused(g, 401, 2.5);
    assert_eq!(s.stopped(), Some("refused 401"));
    assert!(dials(&mut s, 2.5, 20.0).is_empty());
}

#[test]
fn an_open_between_two_401s_allows_another_retry() {
    let mut s = Session::new("ws://h/ws");
    let g = s.generation();
    s.on_refused(g, 401, 0.0);
    dials(&mut s, 0.0, 2.0);
    s.on_open(g);
    s.on_close(g, 1006, 3.0);
    s.on_refused(g, 401, 4.5);
    assert!(s.stopped().is_none());
}

#[test]
fn tokens_are_kept_per_server_and_never_from_a_spectator() {
    let mut s = Session::new("wss://a.example/ws");
    let g = s.generation();
    s.on_welcome(g, Some("TA"), false);
    let g = s.connect("wss://b.example/ws?proto=2");
    assert_eq!(s.dial_url(), "wss://b.example/ws?proto=2", "a's token must not go to b");
    s.on_welcome(g, Some("SPEC"), true);
    assert_eq!(s.dial_url(), "wss://b.example/ws?proto=2");
    s.on_welcome(g, Some("TB"), false);
    assert_eq!(s.dial_url(), "wss://b.example/ws?proto=2&token=TB");
    s.connect("wss://a.example/ws");
    assert_eq!(s.dial_url(), "wss://a.example/ws?token=TA");
}

#[test]
fn a_newer_token_replaces_the_old_one_in_the_url() {
    let mut s = Session::new("ws://h/?proto=1");
    let g = s.generation();
    s.on_welcome(g, Some("T1"), false);
    s.on_welcome(g, Some("T2"), false);
    assert_eq!(s.dial_url(), "ws://h/?proto=1&token=T2");
}

#[test]
fn events_of_an_abandoned_attempt_are_ignored() {
    let mut s = Session::new("ws://a/ws");
    let old = s.generation();
    let new = s.connect("ws://b/ws");
    s.on_close(old, KICKED, 1.0);
    s.on_welcome(old, Some("OLD"), false);
    s.on_refused(old, 403, 1.0);
    assert!(s.stopped().is_none());
    assert_eq!(s.dial_url(), "ws://b/ws");
    s.on_close(new, 1006, 2.0);
    assert_eq!(dials(&mut s, 2.0, 4.0), [(3.0, "ws://b/ws".to_string())]);
}

#[test]
fn connect_clears_a_pending_dial_and_resets_the_delay() {
    let mut s = Session::new("ws://a/ws");
    let g = s.generation();
    for t in [0.0, 1.0, 2.7] {
        s.on_close(g, 1006, t);
    }
    let g2 = s.connect("ws://b/ws");
    assert!(dials(&mut s, 2.7, 10.0).is_empty(), "the old timer is gone");
    s.on_close(g2, 1006, 10.0);
    assert_eq!(dials(&mut s, 10.0, 12.0).first().map(|d| d.0), Some(11.0));
}
