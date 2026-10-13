using System;

namespace Fastengine.Three
{
    public enum ToneMappingMode { None, Linear, Reinhard, AcesFilmic }
    public enum FogMode { None, Linear, Exp2 }

    // What the renderer is set to, as three's renderer.toneMapping, renderer.toneMappingExposure and scene.fog; ToScreen
    // is false when rendering into a render target (three's renderer.getRenderTarget() !== null). Colours are linear.
    public sealed class OutputSettings
    {
        public ToneMappingMode ToneMapping = ToneMappingMode.AcesFilmic;
        public double Exposure = 1;
        public bool ToScreen = true;
        public FogMode Fog = FogMode.None;
        public double[] FogColor = { 1, 1, 1 };
        public double FogNear = 1, FogFar = 1000, FogDensity = 0.00025;
    }

    // fastengine spec B08/B11: the end of three r162's fragment shader (tonemapping_fragment, colorspace_fragment,
    // fog_fragment) on the CPU, so the port's shader can be checked against it. js/three-r162-output.glsl.txt holds
    // three's own GLSL and the code that picks its defines and uniforms.
    public static class OutputColor
    {
        // The colour three writes (0..1 per channel, before the 8-bit store) for an unlit MeshBasicMaterial fragment whose
        // colour is `color` (linear RGB) at view depth `depth`; toneMapped and fog are the material's own flags.
        public static double[] Fragment(double[] color, double depth, OutputSettings s, bool toneMapped = true, bool fog = true)
        {
            var c = (double[])color.Clone();
            if (s.ToneMapping == ToneMappingMode.AcesFilmic && s.ToScreen) c = Aces(c, s.Exposure);
            if (s.ToScreen) for (int i = 0; i < 3; i++) c[i] = ToSrgb(c[i]);
            if (s.Fog == FogMode.Exp2 && s.FogDensity > 0)
            {
                var f = Math.Clamp(1 - Math.Exp(-s.FogDensity * s.FogDensity * depth * depth), 0, 1);
                for (int i = 0; i < 3; i++) c[i] = c[i] + (s.FogColor[i] - c[i]) * f;
            }
            for (int i = 0; i < 3; i++) c[i] = Math.Clamp(c[i], 0, 1);
            return c;
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
            for (int i = 0; i < 3; i++) v[i] = (v[i] * (v[i] + 0.0245786) - 0.000090537) / (v[i] * (0.983729 * v[i] + 0.4329510) + 0.238081);
            return new[]
            {
                Math.Clamp(1.60475 * v[0] - 0.53108 * v[1] - 0.07367 * v[2], 0, 1),
                Math.Clamp(-0.10208 * v[0] + 1.10813 * v[1] - 0.00605 * v[2], 0, 1),
                Math.Clamp(-0.00327 * v[0] - 0.07276 * v[1] + 1.07602 * v[2], 0, 1),
            };
        }

        static double ToSrgb(double x) => x <= 0.0031308 ? x * 12.92 : 1.055 * Math.Pow(x, 1 / 2.4) - 0.055;
    }
}
