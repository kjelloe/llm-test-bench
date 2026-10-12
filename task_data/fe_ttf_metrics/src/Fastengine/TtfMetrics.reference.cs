using System;
using System.Collections.Generic;

namespace Fastengine
{
    // Adapted from fastengine's Fonts.cs (Cmap, Advances, Metrics).
    public sealed class TtfMetrics
    {
        readonly byte[] _d;
        readonly Dictionary<int, int> _cmap;
        readonly int _hmtx, _numberOfHMetrics;

        public TtfMetrics(byte[] ttf)
        {
            _d = ttf;
            int head = Table("head"), hhea = Table("hhea");
            UnitsPerEm = U16(head + 18);
            Ascent = (short)U16(hhea + 4) / (float)UnitsPerEm;
            Descent = -(short)U16(hhea + 6) / (float)UnitsPerEm;
            _numberOfHMetrics = U16(hhea + 34);
            _hmtx = Table("hmtx");
            _cmap = Cmap();
        }

        public int UnitsPerEm { get; }
        public float Ascent { get; }
        public float Descent { get; }

        public int GlyphId(int codepoint) => _cmap.TryGetValue(codepoint, out var g) ? g : 0;

        // Glyphs past numberOfHMetrics share the last advance (monospaced fonts store only a few).
        public float AdvanceEm(int codepoint) =>
            U16(_hmtx + 4 * Math.Min(GlyphId(codepoint), _numberOfHMetrics - 1)) / (float)UnitsPerEm;

        public float MeasureCss(string text, float cssPx)
        {
            float em = 0;
            for (int i = 0; i < text.Length; i++)
            {
                int cp = char.ConvertToUtf32(text, i);
                if (char.IsHighSurrogate(text[i])) i++;
                em += AdvanceEm(cp);
            }
            return em * cssPx;
        }

        int U16(int o) => _d[o] << 8 | _d[o + 1];
        long U32(int o) => (long)_d[o] << 24 | (long)_d[o + 1] << 16 | (long)_d[o + 2] << 8 | _d[o + 3];

        // Format 12 (all of Unicode) when the font has one, else format 4 (the BMP).
        Dictionary<int, int> Cmap()
        {
            int cmap = Table("cmap"), format4 = -1, format12 = -1;
            for (int i = 0; i < U16(cmap + 2); i++)
            {
                int sub = cmap + (int)U32(cmap + 8 + 8 * i), format = U16(sub);
                if (format == 12) format12 = sub;
                else if (format == 4 && format4 < 0) format4 = sub;
            }
            var map = new Dictionary<int, int>();
            if (format12 >= 0)
            {
                for (long g = 0; g < U32(format12 + 12); g++)
                {
                    int rec = format12 + 16 + 12 * (int)g;
                    long start = U32(rec), end = U32(rec + 4), glyph = U32(rec + 8);
                    for (long c = start; c <= end; c++) map[(int)c] = (int)(glyph + c - start);
                }
                return map;
            }
            int segments = U16(format4 + 6) / 2;
            int ends = format4 + 14, starts = ends + 2 * segments + 2, deltas = starts + 2 * segments, offsets = deltas + 2 * segments;
            for (int s = 0; s < segments; s++)
            {
                int end = U16(ends + 2 * s), start = U16(starts + 2 * s), delta = U16(deltas + 2 * s), offset = U16(offsets + 2 * s);
                for (int c = start; c <= end && c != 0xFFFF; c++)
                {
                    int glyph = offset == 0 ? (c + delta) & 0xFFFF : U16(offsets + 2 * s + offset + 2 * (c - start));
                    if (offset != 0 && glyph != 0) glyph = (glyph + delta) & 0xFFFF;
                    if (glyph != 0) map[c] = glyph;
                }
            }
            return map;
        }

        int Table(string tag)
        {
            int count = _d[4] << 8 | _d[5];
            for (int i = 0; i < count; i++)
            {
                int rec = 12 + 16 * i;
                if (_d[rec] == tag[0] && _d[rec + 1] == tag[1] && _d[rec + 2] == tag[2] && _d[rec + 3] == tag[3])
                    return _d[rec + 8] << 24 | _d[rec + 9] << 16 | _d[rec + 10] << 8 | _d[rec + 11];
            }
            throw new InvalidOperationException($"font has no {tag} table");
        }
    }
}
