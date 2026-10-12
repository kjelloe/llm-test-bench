using System;
using System.Globalization;

namespace Fastengine
{
    public readonly record struct Rgba(byte R, byte G, byte B, byte A);

    // CSS colours from the browser game's styles and canvas calls, parsed the way a browser does.
    // This is the first version from the port (it covered the HUD's first screens only).
    public static class CssColor
    {
        // How many strings have actually been parsed (not answered from the cache).
        public static int ParseCount { get; private set; }

        // The colour, or null when the browser would reject the string.
        public static Rgba? Parse(string css)
        {
            ParseCount++;
            css = css.Trim();
            if (css.StartsWith('#'))
            {
                var hex = css[1..];
                if (hex.Length == 3) hex = $"{hex[0]}{hex[0]}{hex[1]}{hex[1]}{hex[2]}{hex[2]}";
                var v = int.Parse(hex, NumberStyles.HexNumber);
                return new Rgba((byte)(v >> 16), (byte)(v >> 8), (byte)v, 255);
            }
            var open = css.IndexOf('(');
            var parts = css[(open + 1)..css.IndexOf(')')].Split(',');
            float P(int i) => float.Parse(parts[i].Trim(), CultureInfo.InvariantCulture);
            return new Rgba((byte)P(0), (byte)P(1), (byte)P(2), (byte)Math.Round((parts.Length > 3 ? P(3) : 1) * 255, MidpointRounding.AwayFromZero));
        }
    }
}
