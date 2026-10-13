using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Ease values come from an exact double-precision solve of cubic-bezier(0.25, 0.1, 0.25, 1), not from the port.
    public class ViewMathTests
    {
        static void Near(double want, double got, string what, double tol = 1e-3) =>
            Assert.True(Math.Abs(want - got) <= tol, $"{what}: {got}, expected {want}");

        static void Is(Rect r, float x, float y, float w, float h, string what)
        {
            Near(x, r.X, what + " x"); Near(y, r.Y, what + " y"); Near(w, r.Width, what + " width"); Near(h, r.Height, what + " height");
        }

        [Fact]
        public void Fit_Letterboxes()
        {
            Is(ViewMath.Fit(3840, 2160, 1280, 720), 0, 0, 3840, 2160, "same shape fills");
            Is(ViewMath.Fit(1024, 768, 1280, 720), 0, 96, 1024, 576, "bars above and below");
            Is(ViewMath.Fit(2560, 1080, 1280, 720), 320, 0, 1920, 1080, "bars at the sides");
            Is(ViewMath.Fit(800, 480, 800, 480), 0, 0, 800, 480, "exact size");
            Is(ViewMath.Fit(640, 480, 1280, 720), 0, 60, 640, 360, "smaller than the render");
        }

        [Fact]
        public void Mouse_MapsBackThroughTheSameRectangle()
        {
            var view = ViewMath.Fit(1024, 768, 1280, 720);
            var (x, y) = ViewMath.ToOutput(512, 384, view, 1280, 720, 1);
            Near(640, x, "centre x"); Near(360, y, "centre y");
            (x, y) = ViewMath.ToOutput(0, 96, view, 1280, 720, 1);
            Near(0, x, "top-left x"); Near(0, y, "top-left y");
            (x, y) = ViewMath.ToOutput(1024, 672, view, 1280, 720, 1.25f);
            Near(1024, x, "bottom-right x at UI scale 1.25"); Near(576, y, "bottom-right y at UI scale 1.25");
            (x, y) = ViewMath.ToOutput(100, 10, view, 1280, 720, 1);
            Assert.True(y < 0, $"a point in the top bar maps above the render (y = {y})");
            view = ViewMath.Fit(2560, 1080, 1280, 720);
            (x, y) = ViewMath.ToOutput(320 + 960, 540, view, 1280, 720, 2);
            Near(320, x, "side bars, UI scale 2: x"); Near(180, y, "side bars, UI scale 2: y");
        }

        [Fact]
        public void Zoom_StepsThroughBrowserLevels()
        {
            Near(1.1f, ViewMath.NextZoom(1, 1), "1 up"); Near(0.9f, ViewMath.NextZoom(1, -1), "1 down");
            Near(3, ViewMath.NextZoom(3, 1), "top clamps"); Near(0.5f, ViewMath.NextZoom(0.5f, -1), "bottom clamps");
            Near(1.25f, ViewMath.NextZoom(1.3f, -1), "between levels, down"); Near(1.5f, ViewMath.NextZoom(1.3f, 1), "between levels, up");
            Near(0.75f, ViewMath.NextZoom(0.67f, 1), "0.67 up");
            Near(0.75f, ViewMath.NextZoom(0.6705f, 1), "within 0.001 of 0.67 counts as 0.67, up");
            Near(0.5f, ViewMath.NextZoom(0.6695f, -1), "within 0.001 of 0.67 counts as 0.67, down");
            Near(0.67f, ViewMath.NextZoom(0.6667f, 1), "0.6667 is below the 0.67 level: up goes to 0.67");
            Near(0.75f, ViewMath.NextZoom(0.6695f, 1), "0.6695 counts as 0.67: up skips to 0.75");
            Near(0.5f, ViewMath.NextZoom(0.6705f, -1), "0.6705 counts as 0.67: down skips to 0.5");
            Near(3, ViewMath.NextZoom(7, 1), "above the top"); Near(3, ViewMath.NextZoom(7, -1), "above the top, down");
            Near(0.5f, ViewMath.NextZoom(0.1f, -1), "below the bottom"); Near(0.5f, ViewMath.NextZoom(0.1f, 1), "below the bottom, up");
        }

        [Theory]
        [InlineData(0, 0)]
        [InlineData(1, 1)]
        [InlineData(-0.5, 0)]
        [InlineData(1.5, 1)]
        [InlineData(0.1, 0.094796)]
        [InlineData(0.25, 0.408511)]
        [InlineData(0.4, 0.682541)]
        [InlineData(0.5, 0.802403)]
        [InlineData(0.6, 0.885229)]
        [InlineData(0.75, 0.960459)]
        [InlineData(0.9, 0.994316)]
        [InlineData(0.99, 0.999946)]
        public void Ease_IsTheCssCurve(double t, double want) => Near(want, ViewMath.Ease((float)t), $"ease({t})");

        [Fact]
        public void Transition_RunsAndHolds()
        {
            var f = new CssTransition(0.2);
            Near(0, f.Value(0), "starts off"); Assert.False(f.On);
            f.Set(true, 1.0);
            Assert.True(f.On);
            Near(0, f.Value(1.0), "at the start");
            Near(0.802403, f.Value(1.1), "halfway in time");
            Near(1, f.Value(1.2), "at the end"); Near(1, f.Value(9), "holds");
            f.Set(true, 1.3);
            Near(1, f.Value(1.3), "Set to the same state changes nothing");
            var g = new CssTransition(0.2);
            g.Set(true, 5.0);
            g.Set(true, 5.05);                      // again while rising: must not restart the curve
            Near(0.802403, g.Value(5.1), "Set on while rising changes nothing");
            f.Set(false, 2.0);
            Near(1 - 0.802403, f.Value(2.1), "full reversal, halfway"); Near(0, f.Value(2.2), "full reversal, end");
        }

        [Fact]
        public void Transition_TurnedAroundMidway_RunsFromWhereItIs()
        {
            var f = new CssTransition(0.2);
            f.Set(true, 10.0);
            double v = 0.408511;                    // ease(0.25) at a quarter of the duration
            Near(v, f.Value(10.05), "a quarter in");
            f.Set(false, 10.05);
            Near(v, f.Value(10.05), "no jump when turned around");
            double span = 0.2 * v;                  // the reversing shortening factor
            Near(v * (1 - 0.802403), f.Value(10.05 + span / 2), "half of the shortened span, eased again");
            Near(0, f.Value(10.05 + span), "done after the shortened span", 1e-6);
            Near(0, f.Value(10.05 + span + 0.5), "holds");
        }
    }
}
