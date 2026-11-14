//! Reference: grid-based, one tick per frame at most, missed beats dropped.

pub struct TickClock {
    interval_ms: f64,
    start_ms: Option<f64>,
    beats_done: i64,
    paused: bool,
}

impl TickClock {
    pub fn new(interval_ms: f64) -> Self {
        TickClock { interval_ms, start_ms: None, beats_done: 0, paused: false }
    }

    pub fn frame(&mut self, now_ms: f64) -> u32 {
        let start = match self.start_ms {
            None => {
                self.start_ms = Some(now_ms);
                self.beats_done = 0;
                return 0;
            }
            Some(s) => s,
        };
        if self.paused {
            return 0;
        }
        let due = ((now_ms - start) / self.interval_ms).floor() as i64;
        if due > self.beats_done {
            self.beats_done = due;
            1
        } else {
            0
        }
    }

    pub fn pause(&mut self) {
        self.paused = true;
    }

    pub fn resume(&mut self, now_ms: f64) {
        self.paused = false;
        self.start_ms = Some(now_ms);
        self.beats_done = 0;
    }
}
