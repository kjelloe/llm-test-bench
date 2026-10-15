using System;

namespace GameClient
{
    // Unity port of the browser loop in js/main-loop.js. In the browser, setInterval(TICK_MS) runs pred.tick()
    // at 20 Hz on its own timer while requestAnimationFrame renders. Unity has only the frame loop, so Update()
    // calls Frame(Time.unscaledDeltaTime) and this class runs the ticks that fell due.
    public sealed class TickDriver
    {
        public const double TickSeconds = 0.05;
        public const int MaxTicksPerFrame = 5;

        readonly Action _tick;
        float _elapsed;

        public TickDriver(Action tick)
        {
            _tick = tick ?? throw new ArgumentNullException(nameof(tick));
        }

        public long Ticks { get; private set; }

        // Fraction of the next tick that has elapsed, for drawing between the last two predicted positions.
        public float Alpha => 0f;

        public void Frame(float unscaledDeltaTime)
        {
            _elapsed += unscaledDeltaTime;
            if (_elapsed >= TickSeconds)
            {
                _elapsed = 0f;
                Ticks++;
                _tick();
            }
        }

        // From OnApplicationPause / OnApplicationFocus.
        public void Pause(bool paused)
        {
        }
    }
}
