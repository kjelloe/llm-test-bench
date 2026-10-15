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
        double _accumulated;
        bool _paused, _skipNextFrame;

        public TickDriver(Action tick)
        {
            _tick = tick ?? throw new ArgumentNullException(nameof(tick));
        }

        public long Ticks { get; private set; }

        public float Alpha => (float)(_accumulated / TickSeconds);

        public void Frame(float unscaledDeltaTime)
        {
            if (_paused) return;
            if (_skipNextFrame) { _skipNextFrame = false; return; }
            if (!(unscaledDeltaTime > 0f) || float.IsInfinity(unscaledDeltaTime)) return;

            _accumulated += unscaledDeltaTime;
            var ran = 0;
            while (_accumulated >= TickSeconds)
            {
                if (ran == MaxTicksPerFrame)
                {
                    _accumulated = 0;
                    break;
                }
                _accumulated -= TickSeconds;
                Ticks++;
                ran++;
                _tick();
            }
        }

        public void Pause(bool paused)
        {
            if (_paused && !paused) _skipNextFrame = true;
            _paused = paused;
        }
    }
}
