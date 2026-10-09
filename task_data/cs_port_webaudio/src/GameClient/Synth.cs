using System;
using System.Collections.Generic;

namespace GameClient
{
    /// <summary>
    /// Offline C# port of boombrawl's client/sound.js (Web Audio): renders each effect to a sample
    /// buffer at 48 kHz so the Unity client sounds like the browser.
    /// </summary>
    public static class Synth
    {
        public const int SampleRate = 48000;

        public static readonly Dictionary<string, Layer[]> Effects = new Dictionary<string, Layer[]>();

        public static double ExponentialRamp(double from, double to, double t, double dur)
        {
            throw new NotImplementedException();
        }

        public static (double b0, double b1, double b2, double a1, double a2) Lowpass(double cutoffHz, double q, int sampleRate)
        {
            throw new NotImplementedException();
        }

        public static float[] Render(Layer[] layers, int seed = 1)
        {
            throw new NotImplementedException();
        }
    }
}
