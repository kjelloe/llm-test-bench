//! The reconnect policy of bj-engine's WebSocket client (bj_core::net), as a state machine on a virtual clock (`now`
//! in seconds). The socket code calls the `on_*` methods; it calls `tick(now)` every frame and dials the URL it
//! returns. Every event carries the generation of the attempt it belongs to; events of an older generation are
//! ignored (an abandoned attempt raises nothing). Once stopped, nothing reconnects until `connect`.
//!
//! - Reconnect timing: after a close, the next dial is due `delay` seconds later. The delay starts at 1.0 s and grows
//!   by ×1.7 after each close, capped at 5.0 s (1, 1.7, 2.89, 4.913, 5, 5, ...); a successful open resets it to 1.0 s.
//! - Close codes 4000 (superseded: another connection took this seat), 4001 (kicked) and 4003 (room closed) are final:
//!   `stopped()` becomes "superseded", "kicked" or "room closed". A kicked client also forgets its seat token for that
//!   server. A superseded session must never resume by itself (it keeps its token for a manual `connect`).
//!   Any other close code reconnects.
//! - A refused upgrade: 403 stops at once ("refused 403"); a 401 is retried once, 2.0 s later, and a second 401 in a row
//!   stops ("refused 401"). An open in between resets that.
//! - Seat tokens: a player's welcome gives a token for the current server (its origin, `scheme://host[:port]`); a
//!   spectator's welcome never stores one. `dial_url()` is the current URL with `token=<token>` for its server added
//!   by `with_query` (other query parameters kept, an existing token replaced).
//! - `connect(url)`: a new generation on a (possibly other) server: clears any stop and pending dial, resets the
//!   delay and the 401 retry, keeps the tokens of every server. Returns the new generation.
//! - URL helpers: `without_query` drops the query and fragment; `origin` is `scheme://host[:port]`; `with_query(url,
//!   key, value)` replaces or appends one parameter and adds the "/" path a bare origin needs
//!   (`ws://h` + token=a = `ws://h/?token=a`).
//!
//! This first version reconnects after one second whatever happened and appends the token blindly.
pub fn without_query(url: &str) -> &str {
    url.split('?').next().unwrap_or(url)
}

pub fn origin(url: &str) -> &str {
    without_query(url)
}

pub fn with_query(url: &str, key: &str, value: &str) -> String {
    if url.contains('?') {
        format!("{url}&{key}={value}")
    } else {
        format!("{url}?{key}={value}")
    }
}

pub const SUPERSEDED: u16 = 4000;
pub const KICKED: u16 = 4001;
pub const ROOM_CLOSED: u16 = 4003;

pub struct Session {
    url: String,
    gen: u32,
    token: Option<String>,
    due: Option<f64>,
    stopped: Option<String>,
}

impl Session {
    pub fn new(url: &str) -> Session {
        Session { url: url.to_string(), gen: 1, token: None, due: None, stopped: None }
    }
    pub fn generation(&self) -> u32 {
        self.gen
    }
    pub fn dial_url(&self) -> String {
        match &self.token {
            Some(t) => with_query(&self.url, "token", t),
            None => self.url.clone(),
        }
    }
    pub fn connect(&mut self, url: &str) -> u32 {
        self.gen += 1;
        self.url = url.to_string();
        self.gen
    }
    pub fn on_open(&mut self, _gen: u32) {}
    pub fn on_welcome(&mut self, _gen: u32, token: Option<&str>, _spectator: bool) {
        if let Some(t) = token {
            self.token = Some(t.to_string());
        }
    }
    pub fn on_close(&mut self, _gen: u32, _code: u16, now: f64) {
        self.due = Some(now + 1.0);
    }
    pub fn on_refused(&mut self, _gen: u32, status: u16, _now: f64) {
        self.stopped = Some(format!("refused {status}"));
    }
    pub fn tick(&mut self, now: f64) -> Option<String> {
        match self.due {
            Some(t) if now > t => {
                self.due = None;
                Some(self.dial_url())
            }
            _ => None,
        }
    }
    pub fn stopped(&self) -> Option<&str> {
        self.stopped.as_deref()
    }
}
