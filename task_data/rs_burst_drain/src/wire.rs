//! The server's text frames (read-only for this task). Every frame is a JSON object whose first key is "type".
//! `decode_snapshot` builds the whole view and is the expensive call (it counts itself in `full_decodes`);
//! `read_events` reads only a snapshot's tick and events.
use crate::json::{self, Value};
use std::cell::Cell;

thread_local!(static FULL_DECODES: Cell<usize> = const { Cell::new(0) });

/// How many times `decode_snapshot` ran on this thread.
pub fn full_decodes() -> usize {
    FULL_DECODES.with(|c| c.get())
}

#[derive(Debug, Clone, PartialEq)]
pub struct Snapshot {
    pub tick: i64,
    pub state_hash: String,
    pub view: Value,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Message {
    pub kind: String,
    pub body: Value,
}

/// The frame's "type" from its first bytes, without parsing the rest; None if it does not start like a message.
pub fn kind(text: &str) -> Option<&str> {
    let rest = text.strip_prefix("{\"type\":\"")?;
    rest.split('"').next()
}

/// Tick and events of a snapshot frame (an absent events list is empty).
pub fn read_events(text: &str) -> Result<(i64, Vec<Value>), String> {
    let v = json::parse(text)?;
    if v.get("type").and_then(Value::as_str) != Some("snapshot") {
        return Err("not a snapshot".into());
    }
    let tick = v.get("tick").and_then(Value::as_i64).ok_or("snapshot without tick")?;
    let events = v.get("view").and_then(|w| w.get("events")).and_then(Value::as_array).cloned().unwrap_or_default();
    Ok((tick, events))
}

/// The whole snapshot. Expensive: the client calls it once per frame, for the view it draws.
pub fn decode_snapshot(text: &str) -> Result<Snapshot, String> {
    FULL_DECODES.with(|c| c.set(c.get() + 1));
    let v = json::parse(text)?;
    if v.get("type").and_then(Value::as_str) != Some("snapshot") {
        return Err("not a snapshot".into());
    }
    Ok(Snapshot {
        tick: v.get("tick").and_then(Value::as_i64).ok_or("snapshot without tick")?,
        state_hash: v.get("stateHash").and_then(Value::as_str).unwrap_or_default().to_string(),
        view: v.get("view").cloned().ok_or("snapshot without view")?,
    })
}

/// Any other message (welcome, lobby, error, ...).
pub fn decode_message(text: &str) -> Result<Message, String> {
    let v = json::parse(text)?;
    let kind = v.get("type").and_then(Value::as_str).ok_or("message without type")?.to_string();
    Ok(Message { kind, body: v })
}
