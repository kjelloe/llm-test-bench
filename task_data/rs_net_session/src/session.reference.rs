//! Reference.
use std::collections::HashMap;

pub fn without_query(url: &str) -> &str {
    url.split(['?', '#']).next().unwrap_or(url)
}

pub fn origin(url: &str) -> &str {
    let base = without_query(url);
    match base.find("://") {
        Some(i) => match base[i + 3..].find('/') {
            Some(j) => &base[..i + 3 + j],
            None => base,
        },
        None => base,
    }
}

pub fn with_query(url: &str, key: &str, value: &str) -> String {
    let (base, query) = match url.split_once('?') {
        Some((b, q)) => (b.to_string(), q.to_string()),
        None => (url.to_string(), String::new()),
    };
    let base = if base.find("://").map_or(false, |i| !base[i + 3..].contains('/')) { format!("{base}/") } else { base };
    let mut parts: Vec<String> = query.split('&').filter(|p| !p.is_empty() && p.split('=').next() != Some(key)).map(str::to_string).collect();
    parts.push(format!("{key}={value}"));
    format!("{base}?{}", parts.join("&"))
}

pub const SUPERSEDED: u16 = 4000;
pub const KICKED: u16 = 4001;
pub const ROOM_CLOSED: u16 = 4003;

pub struct Session {
    url: String,
    gen: u32,
    tokens: HashMap<String, String>,
    next_delay: f64,
    due: Option<f64>,
    retried_401: bool,
    stopped: Option<String>,
}

impl Session {
    pub fn new(url: &str) -> Session {
        Session { url: url.to_string(), gen: 1, tokens: HashMap::new(), next_delay: 1.0, due: None, retried_401: false, stopped: None }
    }
    pub fn generation(&self) -> u32 {
        self.gen
    }
    pub fn dial_url(&self) -> String {
        match self.tokens.get(origin(&self.url)) {
            Some(t) => with_query(&self.url, "token", t),
            None => self.url.clone(),
        }
    }
    pub fn connect(&mut self, url: &str) -> u32 {
        self.gen += 1;
        self.url = url.to_string();
        self.next_delay = 1.0;
        self.due = None;
        self.retried_401 = false;
        self.stopped = None;
        self.gen
    }
    pub fn on_open(&mut self, gen: u32) {
        if gen != self.gen || self.stopped.is_some() {
            return;
        }
        self.next_delay = 1.0;
        self.retried_401 = false;
    }
    pub fn on_welcome(&mut self, gen: u32, token: Option<&str>, spectator: bool) {
        if gen != self.gen || spectator {
            return;
        }
        if let Some(t) = token {
            self.tokens.insert(origin(&self.url).to_string(), t.to_string());
        }
    }
    pub fn on_close(&mut self, gen: u32, code: u16, now: f64) {
        if gen != self.gen || self.stopped.is_some() {
            return;
        }
        match code {
            KICKED => {
                self.tokens.remove(origin(&self.url));
                self.stop("kicked");
            }
            SUPERSEDED => self.stop("superseded"),
            ROOM_CLOSED => self.stop("room closed"),
            _ => {
                self.due = Some(now + self.next_delay);
                self.next_delay = (self.next_delay * 1.7).min(5.0);
            }
        }
    }
    pub fn on_refused(&mut self, gen: u32, status: u16, now: f64) {
        if gen != self.gen || self.stopped.is_some() {
            return;
        }
        if status == 401 && !self.retried_401 {
            self.retried_401 = true;
            self.due = Some(now + 2.0);
        } else {
            self.stop(&format!("refused {status}"));
        }
    }
    pub fn tick(&mut self, now: f64) -> Option<String> {
        match self.due {
            Some(t) if now >= t => {
                self.due = None;
                Some(self.dial_url())
            }
            _ => None,
        }
    }
    pub fn stopped(&self) -> Option<&str> {
        self.stopped.as_deref()
    }
    fn stop(&mut self, why: &str) {
        self.stopped = Some(why.to_string());
        self.due = None;
    }
}
