using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Tests for CssColor.Parse (src/Fastengine/CssColor.cs, fastengine's HUD colour parser). This first test passed the
    // first time it ran.
    public class CssColorTests
    {
        [Fact]
        public void ParsesSixDigitHex() => Assert.Equal(new Rgba(255, 0, 0, 255), CssColor.Parse("#ff0000"));
    }
}
