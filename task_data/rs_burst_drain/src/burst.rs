//! One rendered frame's worth of server frames. At ×16 time compression the server sends up to 16 full snapshots per
//! 50 ms, so several arrive between two frames. The client draws only the newest view, but every snapshot's events
//! drive sound and the battle log, so none may be lost.
//!
//! `drain(texts)` gets the frame's text frames in arrival order and returns:
//! - `events`: the events of EVERY snapshot, each tagged with its snapshot's tick, in arrival order (snapshot by
//!   snapshot, and in each snapshot in the order the server listed them). Read them with `wire::read_events`.
//! - `newest`: the newest drawable snapshot, decoded with `wire::decode_snapshot` — the expensive call, so it runs
//!   once per frame when the newest snapshot decodes. A welcome starts a new session: snapshots that arrived before
//!   the last welcome are not drawable (their events are still kept). If the newest drawable snapshot cannot be decoded,
//!   it is reported in `bad` and the one before it is tried instead.
//! - `others`: every other message (welcome, lobby, ...), decoded with `wire::decode_message`, in arrival order.
//! - `snapshots`: how many snapshot frames were read.
//! - `bad`: (index, error) for every frame that could not be read, in index order; the other frames are still handled.
//!
//! This first cut decodes every snapshot in full and keeps only the last one, events included: at ×16 the battle log
//! missed most events.
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
    for (i, text) in texts.iter().enumerate() {
        if wire::kind(text) == Some("snapshot") {
            match wire::decode_snapshot(text) {
                Ok(s) => {
                    out.snapshots += 1;
                    out.newest = Some(s);
                }
                Err(e) => {
                    out.bad.push((i, e));
                    return out;
                }
            }
        } else if let Ok(m) = wire::decode_message(text) {
            out.others.push(m);
        }
    }
    if let Some(s) = &out.newest {
        let events = s.view.get("events").and_then(Value::as_array).cloned().unwrap_or_default();
        out.events = events.into_iter().map(|e| (s.tick, e)).collect();
    }
    out
}
