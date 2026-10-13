using System;

namespace Fastengine.Three
{
    public enum ToneMappingMode { None, Linear, Reinhard, AcesFilmic }
    public enum FogMode { None, Linear, Exp2 }

    public sealed class OutputSettings
    {
        public ToneMappingMode ToneMapping = ToneMappingMode.AcesFilmic;
        public double Exposure = 1;
        public bool ToScreen = true;
        public FogMode Fog = FogMode.None;
        public double[] FogColor = { 1, 1, 1 };
        public double FogNear = 1, FogFar = 1000, FogDensity = 0.00025;
    }

    public static class OutputColor
    {
        public static double[] Fragment(double[] color, double depth, OutputSettings s, bool toneMapped = true, bool fog = true)
        {
            var c = (double[])color.Clone();
            var mode = toneMapped && s.ToScreen ? s.ToneMapping : ToneMappingMode.None;
            c = mode switch
            {
                ToneMappingMode.Linear => Map(c, x => Saturate(s.Exposure * x)),
                ToneMappingMode.Reinhard => Map(c, x => Saturate(x * s.Exposure / (1 + x * s.Exposure))),
                ToneMappingMode.AcesFilmic => Aces(c, s.Exposure),
                _ => c,
            };
            if (s.ToScreen) c = Map(c, ToSrgbShader);
            if (fog && s.Fog != FogMode.None)
            {
                var fogColor = s.ToScreen ? Map(s.FogColor, ToSrgbCpu) : s.FogColor;
                double f = s.Fog == FogMode.Exp2
                    ? 1 - Math.Exp(-s.FogDensity * s.FogDensity * depth * depth)
                    : SmoothStep(s.FogNear, s.FogFar, depth);
                for (int i = 0; i < 3; i++) c[i] = c[i] * (1 - f) + fogColor[i] * f;
            }
            return Map(c, Saturate);
        }

        static double[] Map(double[] c, Func<double, double> f) => new[] { f(c[0]), f(c[1]), f(c[2]) };
        static double Saturate(double x) => Math.Clamp(x, 0, 1);

        static double SmoothStep(double e0, double e1, double x)
        {
            var t = Saturate((x - e0) / (e1 - e0));
            return t * t * (3 - 2 * t);
        }

        static double[] Aces(double[] c, double exposure)
        {
            double r = c[0] * exposure / 0.6, g = c[1] * exposure / 0.6, b = c[2] * exposure / 0.6;
            double[] v =
            {
                0.59719 * r + 0.35458 * g + 0.04823 * b,
                0.07600 * r + 0.90834 * g + 0.01566 * b,
                0.02840 * r + 0.13383 * g + 0.83777 * b,
            };
            v = Map(v, x => (x * (x + 0.0245786) - 0.000090537) / (x * (0.983729 * x + 0.4329510) + 0.238081));
            return Map(new[]
            {
                1.60475 * v[0] - 0.53108 * v[1] - 0.07367 * v[2],
                -0.10208 * v[0] + 1.10813 * v[1] - 0.00605 * v[2],
                -0.00327 * v[0] - 0.07276 * v[1] + 1.07602 * v[2],
            }, Saturate);
        }

        // sRGBTransferOETF in the shader (the GLSL mix picks per channel) and LinearToSRGB on the CPU: the same curve.
        static double ToSrgbShader(double x) => x <= 0.0031308 ? x * 12.92 : Math.Pow(x, 0.41666) * 1.055 - 0.055;
        static double ToSrgbCpu(double x) => x < 0.0031308 ? x * 12.92 : 1.055 * Math.Pow(x, 0.41666) - 0.055;
    }
}
