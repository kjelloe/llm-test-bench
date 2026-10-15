using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    public class CssAlphaTests
    {
        // fixtures.json: pixels Chromium drew for each CSS rgba() panel over an opaque backdrop (a screenshot read back),
        // and the exact linear-light blend, written by tools/make_fixtures.reference.mjs.
        public record Case(Color32 Css, float Alpha, Color32 Backdrop, Color32 Browser, Color32 Linear)
        {
            public override string ToString() => $"rgba({Css.r},{Css.g},{Css.b},{Alpha}) over rgb({Backdrop.r},{Backdrop.g},{Backdrop.b})";
        }

        static Color32 C(JsonElement a) => new Color32((byte)a[0].GetInt32(), (byte)a[1].GetInt32(), (byte)a[2].GetInt32(), 255);

        static readonly Case[] Cases = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "../../../fixtures.json")))
            .RootElement.EnumerateArray()
            .Select(e => new Case(C(e.GetProperty("css")), e.GetProperty("alpha").GetSingle(), C(e.GetProperty("backdrop")),
                C(e.GetProperty("browser")), C(e.GetProperty("linear"))))
            .ToArray();

        static int MaxChannelDiff(Color32 a, Color32 b) => new[] { Math.Abs(a.r - b.r), Math.Abs(a.g - b.g), Math.Abs(a.b - b.b) }.Max();

        static double Lin(byte c) { var v = c / 255.0; return v <= 0.04045 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4); }

        // Luminance (Rec. 709 weights in linear light), expressed back as an sRGB level 0-255.
        static double Luma(Color32 c)
        {
            var y = 0.2126 * Lin(c.r) + 0.7152 * Lin(c.g) + 0.0722 * Lin(c.b);
            return 255 * (y <= 0.0031308 ? y * 12.92 : 1.055 * Math.Pow(y, 1 / 2.4) - 0.055);
        }

        [Fact]
        public void BrowserOver_MatchesWhatChromiumDraws()
        {
            var bad = Cases.Where(c => MaxChannelDiff(CssAlpha.BrowserOver(c.Backdrop, c.Css, c.Alpha), c.Browser) > 1).ToList();
            Assert.True(bad.Count == 0, $"{bad.Count}/{Cases.Length} more than one level off Chromium, e.g. {bad.FirstOrDefault()}: "
                + (bad.Count > 0 ? $"{CssAlpha.BrowserOver(bad[0].Backdrop, bad[0].Css, bad[0].Alpha)} vs {bad[0].Browser}" : ""));
            Assert.All(Cases, c => Assert.Equal(255, CssAlpha.BrowserOver(c.Backdrop, c.Css, c.Alpha).a));
        }

        [Fact]
        public void LinearOver_BlendsInLinearLight()
        {
            var bad = Cases.Where(c => MaxChannelDiff(CssAlpha.LinearOver(c.Backdrop, c.Css, c.Alpha), c.Linear) > 1).ToList();
            Assert.True(bad.Count == 0, $"{bad.Count}/{Cases.Length} off the linear blend, e.g. {bad.FirstOrDefault()}: "
                + (bad.Count > 0 ? $"{CssAlpha.LinearOver(bad[0].Backdrop, bad[0].Css, bad[0].Alpha)} vs {bad[0].Linear}" : ""));
        }

        [Fact]
        public void AlphaForLinear_ReproducesTheBrowserLuminance()
        {
            var bad = Cases.Where(c =>
            {
                var a = CssAlpha.AlphaForLinear(c.Css, c.Alpha, c.Backdrop);
                return !(a >= 0 && a <= 1) || Math.Abs(Luma(CssAlpha.LinearOver(c.Backdrop, c.Css, a)) - Luma(c.Browser)) > 3;
            }).ToList();
            Assert.True(bad.Count == 0, $"{bad.Count}/{Cases.Length} more than 3 luminance levels off the browser, e.g. {bad.FirstOrDefault()}");
        }

        [Fact]
        public void AlphaForLinear_GrayOnGray_MatchesEveryChannel()
        {
            foreach (var c in Cases.Where(c => c.Css.r == c.Css.g && c.Css.g == c.Css.b && c.Backdrop.r == c.Backdrop.g && c.Backdrop.g == c.Backdrop.b))
            {
                var a = CssAlpha.AlphaForLinear(c.Css, c.Alpha, c.Backdrop);
                Assert.True(MaxChannelDiff(CssAlpha.LinearOver(c.Backdrop, c.Css, a), c.Browser) <= 2, $"{c}: alpha {a}");
            }
        }

        [Fact]
        public void DarkPanels_NeedMoreAlpha_BrightChips_Less()
        {
            var dark = new Color32(0, 0, 0, 255);
            var white = new Color32(255, 255, 255, 255);
            Assert.True(CssAlpha.AlphaForLinear(dark, 0.5f, new Color32(200, 210, 220, 255)) > 0.5f);
            Assert.True(CssAlpha.AlphaForLinear(white, 0.2f, new Color32(20, 30, 50, 255)) < 0.2f);
        }

        [Theory]
        [InlineData(0f)]
        [InlineData(1f)]
        public void EndpointAlphas_StayPut(float alpha)
        {
            var css = new Color32(255, 80, 0, 255);
            var bd = new Color32(20, 30, 50, 255);
            Assert.Equal(alpha, CssAlpha.AlphaForLinear(css, alpha, bd), 3);
        }

        [Fact]
        public void SameLuminanceAsTheBackdrop_KeepsTheCssAlpha_AndStaysInRange()
        {
            var gray = new Color32(128, 128, 128, 255);
            Assert.Equal(0.4f, CssAlpha.AlphaForLinear(gray, 0.4f, gray), 4);
            var a = CssAlpha.AlphaForLinear(new Color32(255, 0, 0, 255), 0.9f, new Color32(0, 255, 0, 255));
            Assert.InRange(a, 0f, 1f);
        }
    }
}
