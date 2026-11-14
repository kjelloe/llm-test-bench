//! Reference.
#[derive(Debug, Clone, Copy)]
enum Kind {
    Set,
    Linear,
    Exponential,
    Target(f64),
}

#[derive(Debug, Clone, Copy)]
struct Event {
    kind: Kind,
    value: f64,
    time: f64,
}

pub struct Param {
    default: f64,
    events: Vec<Event>,
}

impl Param {
    pub fn new(default: f32) -> Self {
        Param { default: default as f64, events: Vec::new() }
    }
    fn insert(&mut self, e: Event) {
        let at = self.events.iter().position(|x| x.time > e.time).unwrap_or(self.events.len());
        self.events.insert(at, e);
    }
    pub fn set_value_at_time(&mut self, value: f32, time: f64) {
        self.insert(Event { kind: Kind::Set, value: value as f64, time });
    }
    pub fn linear_ramp_to_value_at_time(&mut self, value: f32, time: f64) {
        self.insert(Event { kind: Kind::Linear, value: value as f64, time });
    }
    pub fn exponential_ramp_to_value_at_time(&mut self, value: f32, time: f64) {
        self.insert(Event { kind: Kind::Exponential, value: value as f64, time });
    }
    pub fn set_target_at_time(&mut self, target: f32, time: f64, time_constant: f64) {
        self.insert(Event { kind: Kind::Target(time_constant), value: target as f64, time });
    }

    pub fn value_at(&self, t: f64) -> f32 {
        // (time, value) where the current segment starts, and the value just before each event
        let mut start_t = 0.0;
        let mut start_v = self.default;
        let mut target: Option<(f64, f64, f64)> = None; // (v0, t0, tc) with value field below
        let mut target_value = 0.0;
        for e in &self.events {
            // value of the running curve at this event's time
            let at_event = |tt: f64| -> f64 {
                match target {
                    Some((v0, t0, tc)) => target_value + (v0 - target_value) * (-(tt - t0) / tc).exp(),
                    None => start_v,
                }
            };
            match e.kind {
                Kind::Linear | Kind::Exponential => {
                    let (v0, t0) = match target {
                        Some(_) => (at_event(start_t), start_t),
                        None => (start_v, start_t),
                    };
                    if t < e.time {
                        if t < t0 {
                            return at_event(t) as f32;
                        }
                        let k = (t - t0) / (e.time - t0);
                        let v = match e.kind {
                            Kind::Linear => v0 + (e.value - v0) * k,
                            _ if v0 == 0.0 || v0 * e.value < 0.0 => v0,
                            _ => v0 * (e.value / v0).powf(k),
                        };
                        return v as f32;
                    }
                    target = None;
                    start_t = e.time;
                    start_v = e.value;
                }
                Kind::Set => {
                    if t < e.time {
                        return at_event(t) as f32;
                    }
                    target = None;
                    start_t = e.time;
                    start_v = e.value;
                }
                Kind::Target(tc) => {
                    if t < e.time {
                        return at_event(t) as f32;
                    }
                    let v0 = at_event(e.time);
                    target = Some((v0, e.time, tc));
                    target_value = e.value;
                    start_t = e.time;
                    start_v = v0;
                }
            }
        }
        match target {
            Some((v0, t0, tc)) => (target_value + (v0 - target_value) * (-(t - t0) / tc).exp()) as f32,
            None => start_v as f32,
        }
    }

    pub fn render(&self, sample_rate: f64, frames: usize) -> Vec<f32> {
        (0..frames).map(|i| self.value_at(i as f64 / sample_rate)).collect()
    }
}
