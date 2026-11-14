//! The game's input clock, on the native client. The browser client sends input from
//! `setInterval(sendInput, 50)`, and the server keeps one input per 50 ms tick. A native
//! client must emit the ticks the browser would, frame by frame:
//!
//! - The timer runs on a fixed grid: tick k is due at `start + k * interval_ms` (k = 1, 2, ...),
//!   where `start` is the time of the first frame. No tick is due at `start` itself.
//! - At each frame (`frame(now_ms)`, `now_ms` never decreases) the browser runs the timer at most
//!   once: if one or more grid points lie in `(previous frame, now]`, exactly one tick is
//!   emitted and the other missed beats are dropped. A grid point exactly at `now` counts.
//! - Dropped beats are gone: a late frame does not make the next frames tick more often, and
//!   the next tick is still due at the next grid point, not one interval after the late frame.
//! - `pause()` stops the timer (background tab); `resume(now_ms)` restarts it with a new grid
//!   whose start is `now_ms` (like a fresh `setInterval`). Frames while paused emit nothing.
//! - The first `frame` call sets `start` and emits nothing.
//!
//! This first version accumulates elapsed time and catches up on every missed tick, which is
//! what made the native client burst inputs after a hitch.

pub struct TickClock {
    interval_ms: f64,
    last_ms: Option<f64>,
    acc_ms: f64,
    paused: bool,
}

impl TickClock {
    pub fn new(interval_ms: f64) -> Self {
        TickClock { interval_ms, last_ms: None, acc_ms: 0.0, paused: false }
    }

    /// The number of ticks to run in this frame (0 or 1 in the browser).
    pub fn frame(&mut self, now_ms: f64) -> u32 {
        let dt = match self.last_ms {
            None => 0.0,
            Some(last) => now_ms - last,
        };
        self.last_ms = Some(now_ms);
        if self.paused {
            return 0;
        }
        self.acc_ms += dt;
        let mut n = 0;
        while self.acc_ms >= self.interval_ms {
            self.acc_ms -= self.interval_ms;
            n += 1;
        }
        n
    }

    pub fn pause(&mut self) {
        self.paused = true;
    }

    pub fn resume(&mut self, _now_ms: f64) {
        self.paused = false;
    }
}
