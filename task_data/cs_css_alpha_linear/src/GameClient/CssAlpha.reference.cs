using System;
using UnityEngine;

namespace GameClient
{
    // Browsers composite CSS rgba() in sRGB-encoded values; a Unity project in Linear colour space blends in linear
    // light, so the same panel colour and alpha come out lighter over dark scenes (incident F11).
    public static class CssAlpha
    {
        static double ToLinear(byte c)
        {
            var v = c / 255.0;
            return v <= 0.04045 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4);
        }

        static double ToLinear(double srgb255)
        {
            var v = srgb255 / 255.0;
            return v <= 0.04045 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4);
        }

        static byte ToSrgb(double linear)
        {
            var v = linear <= 0.0031308 ? linear * 12.92 : 1.055 * Math.Pow(linear, 1 / 2.4) - 0.055;
            return (byte)Math.Floor(Math.Min(1, Math.Max(0, v)) * 255 + 0.5);
        }

        static double Luminance(double r, double g, double b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;

        public static Color32 BrowserOver(Color32 backdrop, Color32 css, float alpha)
        {
            byte Mix(byte c, byte b) => (byte)Math.Floor(alpha * c + (1 - alpha) * b + 0.5);
            return new Color32(Mix(css.r, backdrop.r), Mix(css.g, backdrop.g), Mix(css.b, backdrop.b), 255);
        }

        public static Color32 LinearOver(Color32 backdrop, Color32 src, float alpha)
        {
            byte Mix(byte c, byte b) => ToSrgb(alpha * ToLinear(c) + (1 - alpha) * ToLinear(b));
            return new Color32(Mix(src.r, backdrop.r), Mix(src.g, backdrop.g), Mix(src.b, backdrop.b), 255);
        }

        public static float AlphaForLinear(Color32 css, float cssAlpha, Color32 backdrop)
        {
            double Target(byte c, byte b) => ToLinear(cssAlpha * c + (1 - cssAlpha) * (double)b);
            var yt = Luminance(Target(css.r, backdrop.r), Target(css.g, backdrop.g), Target(css.b, backdrop.b));
            var ys = Luminance(ToLinear(css.r), ToLinear(css.g), ToLinear(css.b));
            var yd = Luminance(ToLinear(backdrop.r), ToLinear(backdrop.g), ToLinear(backdrop.b));
            if (Math.Abs(ys - yd) < 1e-6) return cssAlpha;
            return (float)Math.Min(1, Math.Max(0, (yt - yd) / (ys - yd)));
        }
    }
}
