using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Expected values follow CSS Color 4 (channels rounded to the nearest integer, halves up; alpha × 255 the same).
    public class CssColorTests
    {
        static void Is(string css, int r, int g, int b, int a = 255)
        {
            var c = CssColor.Parse(css);
            Assert.True(c.HasValue, $"\"{css}\" was rejected");
            Assert.True(c.Value == new Rgba((byte)r, (byte)g, (byte)b, (byte)a), $"\"{css}\" gave {c.Value}, CSS gives ({r}, {g}, {b}, {a})");
        }

        [Fact]
        public void HexForms()
        {
            Is("#abc", 0xaa, 0xbb, 0xcc);
            Is("#ABCDEF", 0xab, 0xcd, 0xef);
            Is("#abcd", 0xaa, 0xbb, 0xcc, 0xdd);
            Is("#11223380", 0x11, 0x22, 0x33, 0x80);
            Is("  #0f0  ", 0, 255, 0);
        }

        [Fact]
        public void RgbLegacyAndModernSyntax()
        {
            Is("rgb(10, 20, 30)", 10, 20, 30);
            Is("rgba(0,0,0,.5)", 0, 0, 0, 128);
            Is("rgb(255 0 0 / 50%)", 255, 0, 0, 128);
            Is("rgb(12 34 56)", 12, 34, 56);
            Is("RGBA(1, 2, 3, 0.25)", 1, 2, 3, 64);
            Is("rgb(0 0 0 / 0)", 0, 0, 0, 0);
        }

        [Fact]
        public void PercentagesRoundingAndClamping()
        {
            Is("rgb(100%, 50%, 0%)", 255, 128, 0);
            Is("rgb(300, -5, 10.6)", 255, 0, 11);
            Is("rgba(0, 0, 0, 1.5)", 0, 0, 0, 255);
            Is("rgb(127.5 0.4 254.5 / 20%)", 128, 0, 255, 51);
        }

        [Fact]
        public void Hsl()
        {
            Is("hsl(120, 100%, 50%)", 0, 255, 0);
            Is("hsl(0 100% 50% / 0.25)", 255, 0, 0, 64);
            Is("hsl(-120deg 100% 25%)", 0, 0, 128);
            Is("hsl(0.5turn 50% 50%)", 64, 191, 191);
            Is("hsla(30, 80%, 60%, 1)", 235, 153, 71);
            Is("hsl(660 25% 90%)", 236, 223, 236);
            Is("hsl(210deg 60% 40%)", 41, 102, 163);
        }

        [Fact]
        public void NamedColours()
        {
            Is("red", 255, 0, 0);
            Is("White", 255, 255, 255);
            Is("transparent", 0, 0, 0, 0);
            Is("orange", 255, 165, 0);
            Is("green", 0, 128, 0);
            Is("grey", 128, 128, 128);
            Is("rebeccapurple", 102, 51, 153);
        }

        [Theory]
        [InlineData("#12")]
        [InlineData("#ggg")]
        [InlineData("#1234567")]
        [InlineData("rgb(1, 2)")]
        [InlineData("rgb(1 2, 3)")]
        [InlineData("blurple")]
        [InlineData("")]
        [InlineData("hsl(120, 100, 50)")]
        public void RejectsWhatBrowsersReject(string css)
        {
            Assert.Null(CssColor.Parse(css));
        }

        [Fact]
        public void ParsesEachStringOnce()
        {
            var before = CssColor.ParseCount;
            for (int i = 0; i < 1000; i++) CssColor.Parse("rgba(12, 34, 56, 0.7)");
            for (int i = 0; i < 1000; i++) CssColor.Parse("#123abc");
            Assert.Equal(before + 2, CssColor.ParseCount);
            Assert.Equal(new Rgba(12, 34, 56, 179), CssColor.Parse("rgba(12, 34, 56, 0.7)"));
        }
    }
}
