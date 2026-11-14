//! A native AudioParam for bj-engine's synth: the sound cues are written for the browser's Web Audio, so a cue rendered
//! natively must match the browser sample for sample. `Param` keeps a timeline of automation events and gives the
//! value at any time, as Web Audio does for an a-rate parameter:
//!
//! - Events are ordered by time, whatever order they were added in; events at the same time keep the order they
//!   were added in.
//! - Before the first event the value is the default.
//! - `set_value_at_time(v, t)`: the value is v from t on.
//! - `linear_ramp_to_value_at_time(v1, t1)` / `exponential_ramp_to_value_at_time(v1, t1)`: a ramp from the previous
//!   event (its time t0 and the value at t0) to v1 at t1. With no previous event the ramp starts at time 0 with the
//!   default value. Linear: `v0 + (v1 - v0) * (t - t0) / (t1 - t0)`. Exponential: `v0 * (v1 / v0)^((t - t0) / (t1 - t0))`;
//!   when v0 is 0, or v0 and v1 have opposite signs, the value stays v0 until t1. The ramp's end value holds from
//!   t >= t1 on (until the next event).
//! - `set_target_at_time(target, t0, tc)`: from t0 the value approaches target exponentially,
//!   `target + (v0 - target) * e^(-(t - t0) / tc)`, v0 being the value at t0; it runs until the next event, which
//!   starts from the curve's value at that event's time.
//! - `render(sample_rate, frames)` gives the value at t = i / sample_rate for each frame i, as f32.
//!
//! This first version renders the cues that only use set and ramp calls in order; others come out wrong or NaN.
#[derive(Debug, Clone, Copy)]
enum Kind {
    Set,
    Linear,
    Exponential,
}

pub struct Param {
    default: f32,
    events: Vec<(Kind, f32, f64)>,
}

impl Param {
    pub fn new(default: f32) -> Self {
        Param { default, events: Vec::new() }
    }
    pub fn set_value_at_time(&mut self, value: f32, time: f64) {
        self.events.push((Kind::Set, value, time));
    }
    pub fn linear_ramp_to_value_at_time(&mut self, value: f32, time: f64) {
        self.events.push((Kind::Linear, value, time));
    }
    pub fn exponential_ramp_to_value_at_time(&mut self, value: f32, time: f64) {
        self.events.push((Kind::Exponential, value, time));
    }
    pub fn set_target_at_time(&mut self, target: f32, time: f64, _time_constant: f64) {
        self.events.push((Kind::Set, target, time));
    }

    pub fn value_at(&self, t: f64) -> f32 {
        let mut v = self.default;
        let mut t0 = 0.0;
        for &(kind, value, time) in &self.events {
            if t <= time {
                let k = ((t - t0) / (time - t0)) as f32;
                return match kind {
                    Kind::Set => v,
                    Kind::Linear => v + (value - v) * k,
                    Kind::Exponential => v * (value / v).powf(k),
                };
            }
            v = value;
            t0 = time;
        }
        v
    }

    pub fn render(&self, sample_rate: f64, frames: usize) -> Vec<f32> {
        (0..frames).map(|i| self.value_at(i as f64 / sample_rate)).collect()
    }
}
