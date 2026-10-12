using System.Text.Json;
using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Fixtures come from an independent reader of the same fonts (fonts/, DejaVu and Liberation, free licences).
    public class TtfMetricsTests
    {
        static readonly JsonElement[] Fonts = JsonDocument.Parse(File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "fixtures.json"))).RootElement.EnumerateArray().ToArray();

        public static IEnumerable<object[]> FontNames() => Fonts.Select(f => new object[] { f.GetProperty("font").GetString() });

        static (TtfMetrics font, JsonElement want) Load(string name) =>
            (new TtfMetrics(File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory, "fonts", name))),
             Fonts.Single(f => f.GetProperty("font").GetString() == name));

        [Theory, MemberData(nameof(FontNames))]
        public void HeadAndHhea(string name)
        {
            var (font, want) = Load(name);
            Assert.Equal(want.GetProperty("unitsPerEm").GetInt32(), font.UnitsPerEm);
            Assert.Equal(want.GetProperty("ascent").GetDouble(), font.Ascent, 5);
            Assert.Equal(want.GetProperty("descent").GetDouble(), font.Descent, 5);
        }

        [Theory, MemberData(nameof(FontNames))]
        public void CmapGlyphIds(string name)
        {
            var (font, want) = Load(name);
            foreach (var g in want.GetProperty("glyphs").EnumerateArray())
            {
                int cp = g.GetProperty("cp").GetInt32();
                Assert.True(g.GetProperty("glyph").GetInt32() == font.GlyphId(cp),
                    $"{name}: U+{cp:X4} maps to glyph {font.GlyphId(cp)}, the cmap says {g.GetProperty("glyph").GetInt32()}");
            }
        }

        [Theory, MemberData(nameof(FontNames))]
        public void AdvanceWidths(string name)
        {
            var (font, want) = Load(name);
            foreach (var g in want.GetProperty("glyphs").EnumerateArray())
            {
                int cp = g.GetProperty("cp").GetInt32();
                double w = g.GetProperty("advanceEm").GetDouble(), got = font.AdvanceEm(cp);
                Assert.True(Math.Abs(w - got) < 1e-5, $"{name}: U+{cp:X4} advance {got} em, hmtx gives {w} em");
            }
        }

        [Theory, MemberData(nameof(FontNames))]
        public void CssTextWidths(string name)
        {
            var (font, want) = Load(name);
            foreach (var t in want.GetProperty("texts").EnumerateArray())
            {
                string text = t.GetProperty("text").GetString();
                float px = (float)t.GetProperty("px").GetDouble();
                double w = t.GetProperty("width").GetDouble(), got = font.MeasureCss(text, px);
                Assert.True(Math.Abs(w - got) < 1e-3, $"{name}: \"{text}\" at {px}px is {got}, expected {w}");
            }
        }

        // A minimal font built here: its cmap's format 4 has a segment that uses both idRangeOffset and idDelta
        // (the bundled fonts never combine them), and only 2 hmtx entries for 3 glyphs.
        static byte[] SyntheticFont()
        {
            var tables = new List<(string tag, byte[] data)>();
            byte[] Be(params int[] u16) => u16.SelectMany(v => new[] { (byte)(v >> 8), (byte)v }).ToArray();
            var head = new byte[54]; head[18] = 1000 >> 8; head[19] = 1000 & 0xFF;
            var hhea = new byte[36]; Array.Copy(Be(800, unchecked((short)-200) & 0xFFFF), 0, hhea, 4, 4); Array.Copy(Be(2), 0, hhea, 34, 2);
            var hmtx = Be(500, 0, 600, 0);
            // format 4: segCount 2; segment 0 maps 'A'..'B' through glyphIdArray (+delta 1), segment 1 is the 0xFFFF end
            var sub = Be(4, 32, 0, 4, 4, 1, 0, /*end*/ 0x42, 0xFFFF, /*pad*/ 0, /*start*/ 0x41, 0xFFFF, /*delta*/ 1, 1,
                         /*rangeOffset*/ 4, 0, /*glyphIdArray*/ 1, 0);
            var cmap = Be(0, 1, 3, 1, 0, 12).Concat(sub).ToArray();
            tables.Add(("cmap", cmap)); tables.Add(("head", head)); tables.Add(("hhea", hhea)); tables.Add(("hmtx", hmtx));
            var font = new List<byte>(Be(1, 0, tables.Count, 0, 0, 0));
            int offset = 12 + 16 * tables.Count;
            var body = new List<byte>();
            foreach (var (tag, data) in tables)
            {
                font.AddRange(System.Text.Encoding.ASCII.GetBytes(tag));
                font.AddRange(new byte[4]);
                int at = offset + body.Count;
                font.AddRange(new[] { (byte)(at >> 24), (byte)(at >> 16), (byte)(at >> 8), (byte)at });
                font.AddRange(new[] { (byte)(data.Length >> 24), (byte)(data.Length >> 16), (byte)(data.Length >> 8), (byte)data.Length });
                body.AddRange(data);
                while (body.Count % 4 != 0) body.Add(0);
            }
            font.AddRange(body);
            return font.ToArray();
        }

        [Fact]
        public void Format4_RangeOffsetWithDelta_AndShortHmtx()
        {
            var font = new TtfMetrics(SyntheticFont());
            Assert.Equal(1000, font.UnitsPerEm);
            Assert.Equal(0.8f, font.Ascent, 5);
            Assert.Equal(0.2f, font.Descent, 5);
            Assert.True(font.GlyphId('A') == 2, $"'A' maps to glyph {font.GlyphId('A')}: glyphIdArray gives 1, plus idDelta 1 = 2");
            Assert.Equal(0, font.GlyphId('B'));   // glyphIdArray holds 0: missing, idDelta is not added
            Assert.Equal(0, font.GlyphId('C'));
            Assert.Equal(0.6f, font.AdvanceEm('A'), 5);   // glyph 2 is past numberOfHMetrics (2): the last advance
            Assert.Equal(0.5f, font.AdvanceEm('B'), 5);   // unmapped: glyph 0
            Assert.Equal(0.6f * 10 + 0.5f * 10, font.MeasureCss("AB", 10), 4);
        }
    }
}
