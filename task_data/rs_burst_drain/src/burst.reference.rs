//! Reference.
use crate::json::Value;
use crate::wire::{self, Message, Snapshot};

#[derive(Debug, Default)]
pub struct Drained {
    pub newest: Option<Snapshot>,
    pub events: Vec<(i64, Value)>,
    pub others: Vec<Message>,
    pub snapshots: usize,
    pub bad: Vec<(usize, String)>,
}

pub fn drain(texts: &[&str]) -> Drained {
    let mut out = Drained::default();
    let last_welcome = texts.iter().rposition(|t| wire::kind(t) == Some("welcome"));
    let mut candidates = Vec::new();
    for (i, text) in texts.iter().enumerate() {
        if wire::kind(text) == Some("snapshot") {
            match wire::read_events(text) {
                Ok((tick, events)) => {
                    out.snapshots += 1;
                    out.events.extend(events.into_iter().map(|e| (tick, e)));
                    if last_welcome.map_or(true, |w| i > w) {
                        candidates.push(i);
                    }
                }
                Err(e) => out.bad.push((i, e)),
            }
        } else {
            match wire::decode_message(text) {
                Ok(m) => out.others.push(m),
                Err(e) => out.bad.push((i, e)),
            }
        }
    }
    for &i in candidates.iter().rev() {
        match wire::decode_snapshot(texts[i]) {
            Ok(s) => {
                out.newest = Some(s);
                break;
            }
            Err(e) => out.bad.push((i, e)),
        }
    }
    out.bad.sort_by_key(|b| b.0);
    out
}
