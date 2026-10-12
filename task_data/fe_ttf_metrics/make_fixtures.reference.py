"""Fixtures for fe_ttf_metrics, from an independent reader of the OpenType tables (written from the spec, not
from the C# reference). Usage: python3 make_fixtures.reference.py > tests/FastengineTests/fixtures.json"""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONTS = ["DejaVuSansMono.ttf", "DejaVuSans-Bold.ttf", "LiberationMono-Regular.ttf"]
CODEPOINTS = [0x20, 0x41, 0x57, 0x61, 0x69, 0x6D, 0x30, 0x2E, 0xC6, 0xD8, 0xC5, 0xE6, 0xF8, 0xE5, 0xE9, 0xDF,
              0x2013, 0x2014, 0x2026, 0x20AC, 0x2212, 0x2022, 0x25B2, 0x2588, 0x4E2D, 0x1D400, 0x1D670, 0x10300, 0x1F600, 0x10FFFF]
TEXTS = ["Hello, world", "WWW iii", "Æøå – 42 €", "Score: 1 234", "−∞ → ▲", "\U0001d670\U0001d671 x", "中文 ok", "😀!"]
SIZES = [11.0, 13.5, 16.0]


class Ttf:
    def __init__(self, data: bytes):
        self.d = data
        count = struct.unpack_from(">H", data, 4)[0]
        self.tables = {}
        for i in range(count):
            tag, _, off, _ = struct.unpack_from(">4sIII", data, 12 + 16 * i)
            self.tables[tag.decode()] = off
        head, hhea = self.tables["head"], self.tables["hhea"]
        self.units_per_em = struct.unpack_from(">H", data, head + 18)[0]
        self.ascender, self.descender = struct.unpack_from(">hh", data, hhea + 4)
        self.num_hmetrics = struct.unpack_from(">H", data, hhea + 34)[0]
        self.cmap = self._cmap()

    def _cmap(self):
        d, base = self.d, self.tables["cmap"]
        subs = {}
        for i in range(struct.unpack_from(">H", d, base + 2)[0]):
            pid, eid, off = struct.unpack_from(">HHI", d, base + 4 + 8 * i)
            subs[(pid, eid)] = base + off
        mapping = {}
        if (3, 10) in subs:                                   # format 12, full Unicode
            sub = subs[(3, 10)]
            assert struct.unpack_from(">H", d, sub)[0] == 12
            for g in range(struct.unpack_from(">I", d, sub + 12)[0]):
                start, end, glyph = struct.unpack_from(">III", d, sub + 16 + 12 * g)
                for c in range(start, end + 1):
                    mapping[c] = glyph + c - start
            return mapping
        sub = subs[(3, 1)]                                    # format 4, BMP
        assert struct.unpack_from(">H", d, sub)[0] == 4
        segs = struct.unpack_from(">H", d, sub + 6)[0] // 2
        ends = sub + 14
        starts = ends + 2 * segs + 2
        deltas = starts + 2 * segs
        offsets = deltas + 2 * segs
        for s in range(segs):
            end, start = struct.unpack_from(">H", d, ends + 2 * s)[0], struct.unpack_from(">H", d, starts + 2 * s)[0]
            delta = struct.unpack_from(">h", d, deltas + 2 * s)[0]
            ro = struct.unpack_from(">H", d, offsets + 2 * s)[0]
            for c in range(start, end + 1):
                if c == 0xFFFF:
                    continue
                if ro == 0:
                    glyph = (c + delta) % 65536
                else:
                    glyph = struct.unpack_from(">H", d, offsets + 2 * s + ro + 2 * (c - start))[0]
                    if glyph:
                        glyph = (glyph + delta) % 65536
                if glyph:
                    mapping[c] = glyph
        return mapping

    def glyph(self, cp):
        return self.cmap.get(cp, 0)

    def advance_units(self, glyph):
        hmtx = self.tables["hmtx"]
        return struct.unpack_from(">H", self.d, hmtx + 4 * min(glyph, self.num_hmetrics - 1))[0]


def codepoints(text):
    return [ord(ch) for ch in text]   # Python str is already one item per code point


out = []
for name in FONTS:
    t = Ttf((ROOT / "fonts" / name).read_bytes())
    out.append({
        "font": name,
        "unitsPerEm": t.units_per_em,
        "ascent": t.ascender / t.units_per_em,
        "descent": -t.descender / t.units_per_em,
        "glyphs": [{"cp": cp, "glyph": t.glyph(cp), "advanceEm": t.advance_units(t.glyph(cp)) / t.units_per_em}
                   for cp in CODEPOINTS],
        "texts": [{"text": s, "px": px,
                   "width": sum(t.advance_units(t.glyph(cp)) for cp in codepoints(s)) / t.units_per_em * px}
                  for s in TEXTS for px in SIZES],
    })
print(json.dumps(out, ensure_ascii=False, indent=0))
