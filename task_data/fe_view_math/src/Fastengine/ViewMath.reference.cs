using System;

namespace Fastengine
{
    public readonly record struct Rect(float X, float Y, float Width, float Height);

    // Adapted from fastengine's App.Fit, App.Mouse, App.NextZoom, Painter.Ease and CssTransition.
    public static class ViewMath
    {
        public static readonly float[] Zooms = { 0.5f, 0.67f, 0.75f, 0.8f, 0.9f, 1, 1.1f, 1.25f, 1.5f, 1.75f, 2, 2.5f, 3 };

        public static Rect Fit(float screenW, float screenH, int width, int height)
        {
            var scale = Math.Min(screenW / width, screenH / height);
            float w = width * scale, h = height * scale;
            return new Rect((screenW - w) / 2, (screenH - h) / 2, w, h);
        }

        public static (float X, float Y) ToOutput(float windowX, float windowY, Rect view, int outW, int outH, float uiScale)
            => ((windowX - view.X) * (outW / view.Width) / uiScale, (windowY - view.Y) * (outH / view.Height) / uiScale);

        public static float NextZoom(float zoom, int step)
        {
            if (step > 0) return Array.Find(Zooms, z => z > zoom + 0.001f) is var up && up > 0 ? up : Zooms[^1];
            var down = Array.FindLast(Zooms, z => z < zoom - 0.001f);
            return down > 0 ? down : Zooms[0];
        }

        public static float Ease(float t)
        {
            if (t <= 0) return 0;
            if (t >= 1) return 1;
            // x(s) = 0.75 s (1 - s) + s^3 rises monotonically: bisect for the s where x(s) = t.
            float lo = 0, hi = 1, s = t;
            for (var i = 0; i < 24; i++)
            {
                s = (lo + hi) / 2;
                if (0.75f * s * (1 - s) + s * s * s < t) lo = s;
                else hi = s;
            }
            return 0.3f * s * (1 - s) * (1 - s) + 3 * s * s * (1 - s) + s * s * s;
        }
    }

    public sealed class CssTransition
    {
        readonly double _duration;
        double _at = double.NegativeInfinity;
        float _from;

        public CssTransition(double duration) => _duration = duration;

        public bool On { get; private set; }

        public void Set(bool on, double now)
        {
            if (on == On) return;
            _from = Value(now);
            On = on;
            _at = now;
        }

        public float Value(double now)
        {
            float to = On ? 1 : 0;
            var span = _duration * Math.Abs(to - _from);
            var k = span <= 0 ? 1 : (now - _at) / span;
            return k >= 1 ? to : _from + (to - _from) * ViewMath.Ease((float)k);
        }
    }
}
