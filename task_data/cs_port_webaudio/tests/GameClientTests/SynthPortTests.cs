using System;
using System.Linq;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // The browser's audio engine cannot run here, so exactness is tested where the Web Audio spec
    // pins the math down (ramps, the lowpass biquad), and the renders are tested for the properties
    // the browser output has: length, starting level, decay to silence, no clipping.
    public class SynthPortTests
    {
        static void Near(double expected, double actual, double tol, string what) =>
            Assert.True(Math.Abs(expected - actual) <= tol, $"{what}: expected {expected}, got {actual}");

        [Fact]
        public void ExponentialRamp_FollowsWebAudioAndHoldsTheEndValue()
        {
            Near(0.15, Synth.ExponentialRamp(0.15, 0.001, 0, 0.07), 1e-12, "start");
            Near(0.15 * Math.Pow(0.001 / 0.15, 0.5), Synth.ExponentialRamp(0.15, 0.001, 0.035, 0.07), 1e-12, "midpoint");
            Near(0.001, Synth.ExponentialRamp(0.15, 0.001, 0.07, 0.07), 1e-12, "end");
            Near(0.001, Synth.ExponentialRamp(0.15, 0.001, 0.2, 0.07), 1e-12, "after the end it holds");
            Near(840 * Math.Pow(105.0 / 840, 0.25), Synth.ExponentialRamp(840, 105, 0.0875, 0.35), 1e-9, "pitch slide");
        }

        // Web Audio spec, BiquadFilterNode "lowpass": Q is in dB here, alpha = sin(w0) / (2 * 10^(Q/20)).
        static (double, double, double, double, double) Spec(double f, double q, int fs)
        {
            double w0 = 2 * Math.PI * f / fs, alpha = Math.Sin(w0) / (2 * Math.Pow(10, q / 20)), c = Math.Cos(w0), a0 = 1 + alpha;
            return ((1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0, -2 * c / a0, (1 - alpha) / a0);
        }

        [Theory]
        [InlineData(840, 1)]
        [InlineData(105, 1)]
        [InlineData(5000, 1)]
        [InlineData(600, 0)]
        [InlineData(1200, 6)]
        public void Lowpass_CoefficientsMatchTheWebAudioSpec(double cutoff, double q)
        {
            var (b0, b1, b2, a1, a2) = Synth.Lowpass(cutoff, q, 48000);
            var (e0, e1, e2, f1, f2) = Spec(cutoff, q, 48000);
            Near(e0, b0, 1e-12, "b0"); Near(e1, b1, 1e-12, "b1"); Near(e2, b2, 1e-12, "b2");
            Near(f1, a1, 1e-12, "a1"); Near(f2, a2, 1e-12, "a2");
        }

        [Fact]
        public void Lowpass_AtTheDefaultQ_BoostsTheCutoffByOneDecibel()
        {
            // Q=1 dB means |H| = 10^(1/20) ~ 1.122 at the cutoff (a linear Q of 1 would give 1.0).
            var (b0, b1, b2, a1, a2) = Synth.Lowpass(1000, 1, 48000);
            double x1 = 0, x2 = 0, y1 = 0, y2 = 0, peak = 0;
            for (int n = 0; n < 48000; n++)
            {
                double x = Math.Sin(2 * Math.PI * 1000 * n / 48000.0);
                double y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
                x2 = x1; x1 = x; y2 = y1; y1 = y;
                if (n > 24000) peak = Math.Max(peak, Math.Abs(y));
            }
            Near(Math.Pow(10, 1 / 20.0), peak, 0.01, "gain at the cutoff");
        }

        [Fact]
        public void Effects_MatchSoundJs()
        {
            Assert.Equal(new[] { "boom", "death", "go", "shrink", "tick", "win" }, Synth.Effects.Keys.OrderBy(k => k).ToArray());
            Layer t = Synth.Effects["tick"].Single();
            Assert.False(t.Noise);
            Assert.Equal((Wave.Square, 880f, 0.07f, 0.12f, 0f), (t.Wave, t.Freq, t.Dur, t.Vol, t.At));
            Layer[] boom = Synth.Effects["boom"];
            Assert.Equal(2, boom.Length);
            Layer nb = boom.Single(l => l.Noise);
            Assert.Equal((0.35f, 0.3f, 420f), (nb.Dur, nb.Vol, nb.Freq));
            Layer bt = boom.Single(l => !l.Noise);
            Assert.Equal((Wave.Sine, 120f, 0.3f, 0.35f, 38f), (bt.Wave, bt.Freq, bt.Dur, bt.Vol, bt.SlideTo));
            Layer[] death = Synth.Effects["death"];
            Layer dn = death.Single(l => l.Noise);
            Assert.Equal((0.25f, 0.12f, 300f, 0.08f), (dn.Dur, dn.Vol, dn.Freq, dn.At));
            Assert.Equal((Wave.Sawtooth, 420f, 70f), (death.Single(l => !l.Noise).Wave, death.Single(l => !l.Noise).Freq, death.Single(l => !l.Noise).SlideTo));
            Assert.Equal(new[] { 0f, 0.11f, 0.22f }, Synth.Effects["go"].Select(l => l.At).ToArray());
            Assert.Equal(new[] { 523f, 659f, 784f }, Synth.Effects["win"].Select(l => l.Freq).ToArray());
            Assert.Equal(new[] { 0f, 0.14f }, Synth.Effects["shrink"].Select(l => l.At).ToArray());
        }

        [Fact]
        public void Render_HasTheBrowserLength_NoClipping_StartsLoud_EndsSilent()
        {
            foreach (var (name, layers) in Synth.Effects)
            {
                float[] s = Synth.Render(layers);
                double expected = layers.Max(l => l.At + l.Dur + (l.Noise ? 0 : 0.02f)) * Synth.SampleRate;
                Assert.True(Math.Abs(s.Length - expected) <= 1, $"{name}: length {s.Length}, expected ~{expected}");
                Assert.True(s.All(v => !float.IsNaN(v) && Math.Abs(v) < 1), $"{name}: NaN or clipping");
                Layer first = layers.OrderBy(l => l.At).First();
                float opening = s.Take(Synth.SampleRate / 100).Max(Math.Abs);
                Assert.True(opening > first.Vol * (first.Noise ? 0.05f : 0.5f), $"{name}: opening peak {opening}");
                float tail = s.Skip(s.Length - Synth.SampleRate / 100).Max(Math.Abs);
                Assert.True(tail < 0.01, $"{name}: tail {tail} is not near silence");
            }
        }

        [Fact]
        public void Render_IsDeterministicForASeed()
        {
            Assert.Equal(Synth.Render(Synth.Effects["boom"], 7), Synth.Render(Synth.Effects["boom"], 7));
        }
    }
}
