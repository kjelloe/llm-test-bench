using System;
using System.Collections.Generic;

namespace GameClient
{
    /// <summary>
    /// Offline C# port of boombrawl's client/sound.js (Web Audio): renders each effect to a sample
    /// buffer at 48 kHz so the Unity client sounds like the browser.
    /// Based on the Unity builder's Synth.cs (unityworks), with the ramp and filter exposed.
    /// </summary>
    public static class Synth
    {
        public const int SampleRate = 48000;

        public static readonly Dictionary<string, Layer[]> Effects = new Dictionary<string, Layer[]>
        {
            ["tick"] = new[] { Layer.Tone(880, 0.07f, 0.12f) },
            ["go"] = new[] { Layer.Tone(440, 0.12f, 0.18f), Layer.Tone(660, 0.12f, 0.18f, at: 0.11f), Layer.Tone(880, 0.22f, 0.2f, at: 0.22f) },
            ["boom"] = new[] { Layer.NoiseBurst(0.35f, 0.3f, 420), Layer.Tone(120, 0.3f, 0.35f, Wave.Sine, 38) },
            ["death"] = new[] { Layer.Tone(420, 0.5f, 0.2f, Wave.Sawtooth, 70), Layer.NoiseBurst(0.25f, 0.12f, 300, 0.08f) },
            ["shrink"] = new[] { Layer.Tone(330, 0.12f, 0.14f), Layer.Tone(220, 0.16f, 0.14f, at: 0.14f) },
            ["win"] = new[] { Layer.Tone(523, 0.14f, 0.16f), Layer.Tone(659, 0.14f, 0.16f, at: 0.13f), Layer.Tone(784, 0.3f, 0.18f, at: 0.26f) },
        };

        // exponentialRampToValueAtTime: v0 * (v1 / v0)^(t / dur), holding v1 afterwards.
        public static double ExponentialRamp(double from, double to, double t, double dur) =>
            from * Math.Pow(to / from, Math.Min(1, t / dur));

        // Web Audio BiquadFilterNode lowpass: Q is in dB, alpha = sin(w0) / (2 * 10^(Q/20)); normalised by a0.
        public static (double b0, double b1, double b2, double a1, double a2) Lowpass(double cutoffHz, double q, int sampleRate)
        {
            var w0 = 2 * Math.PI * cutoffHz / sampleRate;
            var alpha = Math.Sin(w0) / (2 * Math.Pow(10, q / 20.0));
            var cos = Math.Cos(w0);
            var a0 = 1 + alpha;
            return ((1 - cos) / 2 / a0, (1 - cos) / a0, (1 - cos) / 2 / a0, -2 * cos / a0, (1 - alpha) / a0);
        }

        public static float[] Render(Layer[] layers, int seed = 1)
        {
            var length = 0f;
            foreach (var l in layers) length = Math.Max(length, l.At + l.Dur + (l.Noise ? 0 : 0.02f));
            var samples = new float[(int)Math.Ceiling(length * SampleRate)];
            var random = new Random(seed);
            foreach (var l in layers)
            {
                if (l.Noise) AddNoise(samples, l, random);
                else AddTone(samples, l);
            }
            return samples;
        }

        static void AddTone(float[] samples, Layer l)
        {
            var start = (int)(l.At * SampleRate);
            var end = Math.Min(samples.Length, (int)((l.At + l.Dur + 0.02f) * SampleRate));
            var phase = 0.0;
            for (var i = start; i < end; i++)
            {
                var t = (i - start) / (double)SampleRate;
                var freq = l.SlideTo > 0 ? ExponentialRamp(l.Freq, Math.Max(20, l.SlideTo), t, l.Dur) : l.Freq;
                var gain = ExponentialRamp(l.Vol, 0.001, t, l.Dur);
                phase += freq / SampleRate;
                phase -= Math.Floor(phase);
                samples[i] += (float)(gain * Oscillator(l.Wave, phase));
            }
        }

        static double Oscillator(Wave wave, double phase) => wave switch
        {
            Wave.Sine => Math.Sin(2 * Math.PI * phase),
            Wave.Square => phase < 0.5 ? 1 : -1,
            _ => 2 * phase - 1,
        };

        static void AddNoise(float[] samples, Layer l, Random random)
        {
            var start = (int)(l.At * SampleRate);
            var count = (int)Math.Ceiling(SampleRate * l.Dur);
            double x1 = 0, x2 = 0, y1 = 0, y2 = 0;
            for (var n = 0; n < count && start + n < samples.Length; n++)
            {
                var t = n / (double)SampleRate;
                var cutoff = ExponentialRamp(l.Freq * 2, Math.Max(40, l.Freq / 4), t, l.Dur);
                var (b0, b1, b2, a1, a2) = Lowpass(cutoff, 1, SampleRate);
                var x = random.NextDouble() * 2 - 1;
                var y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
                x2 = x1; x1 = x; y2 = y1; y1 = y;
                samples[start + n] += (float)(ExponentialRamp(l.Vol, 0.001, t, l.Dur) * y);
            }
        }
    }
}
