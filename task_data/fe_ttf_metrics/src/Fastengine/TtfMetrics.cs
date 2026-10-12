using System;

namespace Fastengine
{
    // The metrics HUD text layout needs, read straight from a TrueType font's tables (no font library):
    // CSS sizes are em sizes, so widths come from the font's own advances (hmtx) over unitsPerEm (head),
    // and baselines from hhea's ascender/descender. Code points come from the cmap.
    public sealed class TtfMetrics
    {
        readonly byte[] _d;

        public TtfMetrics(byte[] ttf)
        {
            _d = ttf;
            throw new NotImplementedException();
        }

        public int UnitsPerEm { get; }

        // hhea ascender / unitsPerEm.
        public float Ascent { get; }

        // -hhea descender / unitsPerEm (a positive number).
        public float Descent { get; }

        // The glyph id the cmap maps this code point to; 0 (.notdef) when it maps none.
        public int GlyphId(int codepoint) => throw new NotImplementedException();

        // The glyph's advance width (hmtx) over unitsPerEm; an unmapped code point gets glyph 0's advance.
        public float AdvanceEm(int codepoint) => throw new NotImplementedException();

        // Width in CSS px of text set at font-size cssPx: the sum of each code point's advance times cssPx.
        // A character outside the BMP (a UTF-16 surrogate pair) is one code point.
        public float MeasureCss(string text, float cssPx) => throw new NotImplementedException();

        // The byte offset of a table in the font (the table directory follows the 12-byte offset table).
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
