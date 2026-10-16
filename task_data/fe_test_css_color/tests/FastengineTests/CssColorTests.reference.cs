using System;
using Fastengine;
using Xunit;

namespace FastengineTests
{
    // One case per branch the parser takes, values that only the right arithmetic gives (half-way rounding, 4- and
    // 8-digit hex, percentages, negative hue, units), the case rules, whitespace, invalid input, and the parse cache.
    public class CssColorTests
    {
        [Theory]
        [InlineData("#f00", 255, 0, 0, 255)]
        [InlineData("#f008", 255, 0, 0, 136)]
        [InlineData("#11223380", 17, 34, 51, 128)]
        [InlineData("#AbCdEf", 171, 205, 239, 255)]
        [InlineData("RED", 255, 0, 0, 255)]
        [InlineData("RebeccaPurple", 102, 51, 153, 255)]
        [InlineData("transparent", 0, 0, 0, 0)]
        [InlineData("  navy  ", 0, 0, 128, 255)]
        [InlineData("rgb(1, 2, 3)", 1, 2, 3, 255)]
        [InlineData("RGBA(1, 2, 3, 0.5)", 1, 2, 3, 128)]
        [InlineData("rgb(50% 0% 100%)", 128, 0, 255, 255)]
        [InlineData("rgb(75% 25% 10%)", 191, 64, 26, 255)]
        [InlineData("hsl(15 150% 50%)", 255, 64, 0, 255)]
        [InlineData("rgb(10.5 20.5 0 / 50%)", 11, 21, 0, 128)]
        [InlineData("rgb(0 0 0 / 0.25)", 0, 0, 0, 64)]
        [InlineData("hsl(120 100% 50%)", 0, 255, 0, 255)]
        [InlineData("hsl(-120deg 100% 50%)", 0, 0, 255, 255)]
        [InlineData("hsl(0.5turn 100% 50%)", 0, 255, 255, 255)]
        [InlineData("hsl(3.14159265rad 100% 50%)", 0, 255, 255, 255)]
        [InlineData("hsla(240, 100%, 150%, 1)", 255, 255, 255, 255)]
        [InlineData("hsl(0 50% 25% / 40%)", 96, 32, 32, 102)]
        public void Parses(string css, int r, int g, int b, int a) =>
            Assert.Equal(new Rgba((byte)r, (byte)g, (byte)b, (byte)a), CssColor.Parse(css));

        [Theory]
        [InlineData("#ggg")]
        [InlineData("#12345")]
        [InlineData("rgb(1, 2)")]
        [InlineData("rgb(1 2 3 4)")]
        [InlineData("rgb(1, 2, 3 / 0.5)")]
        [InlineData("hsl(120 100 50)")]
        [InlineData("notacolor")]
        [InlineData("")]
        [InlineData("cmyk(1 2 3)")]
        public void RejectsInvalid(string css) => Assert.Null(CssColor.Parse(css));

        [Fact]
        public void ParsesEachStringOnce()
        {
            var key = "rgb(7 8 9 / " + Guid.NewGuid().GetHashCode() % 50 + "%)";
            var before = CssColor.ParseCount;
            var first = CssColor.Parse(key);
            for (var i = 0; i < 10; i++) Assert.Equal(first, CssColor.Parse(key));
            Assert.Equal(before + 1, CssColor.ParseCount);
        }
    }
}
