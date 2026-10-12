using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;

namespace Fastengine
{
    public readonly record struct Rgba(byte R, byte G, byte B, byte A);

    public static class CssColor
    {
        static readonly ConcurrentDictionary<string, Rgba?> Cache = new();
        static int _parses;

        public static int ParseCount => _parses;

        static readonly Dictionary<string, Rgba> Named = new(StringComparer.OrdinalIgnoreCase)
        {
            ["black"] = new(0, 0, 0, 255), ["white"] = new(255, 255, 255, 255), ["red"] = new(255, 0, 0, 255),
            ["green"] = new(0, 128, 0, 255), ["lime"] = new(0, 255, 0, 255), ["blue"] = new(0, 0, 255, 255),
            ["yellow"] = new(255, 255, 0, 255), ["orange"] = new(255, 165, 0, 255), ["gray"] = new(128, 128, 128, 255),
            ["grey"] = new(128, 128, 128, 255), ["silver"] = new(192, 192, 192, 255), ["teal"] = new(0, 128, 128, 255),
            ["navy"] = new(0, 0, 128, 255), ["purple"] = new(128, 0, 128, 255), ["rebeccapurple"] = new(102, 51, 153, 255),
            ["transparent"] = new(0, 0, 0, 0),
        };

        public static Rgba? Parse(string css) => Cache.GetOrAdd(css ?? "", s =>
        {
            System.Threading.Interlocked.Increment(ref _parses);
            return ParseOnce(s.Trim());
        });

        static byte Round(double v) => (byte)Math.Floor(Math.Clamp(v, 0, 255) + 0.5);

        static Rgba? ParseOnce(string s)
        {
            if (s.Length == 0) return null;
            if (s[0] == '#') return Hex(s[1..]);
            if (Named.TryGetValue(s, out var named)) return named;
            int open = s.IndexOf('('), close = s.LastIndexOf(')');
            if (open < 0 || close != s.Length - 1) return null;
            var fn = s[..open].Trim().ToLowerInvariant();
            var body = s[(open + 1)..close].Trim();
            var args = Split(body);
            if (args == null) return null;
            return fn switch
            {
                "rgb" or "rgba" => Rgb(args.Value.parts, args.Value.alpha, args.Value.legacy),
                "hsl" or "hsla" => Hsl(args.Value.parts, args.Value.alpha, args.Value.legacy),
                _ => null,
            };
        }

        static Rgba? Hex(string h)
        {
            foreach (var c in h) if (!Uri.IsHexDigit(c)) return null;
            if (h.Length is 3 or 4) h = string.Concat(System.Linq.Enumerable.Select(h, c => new string(c, 2)));
            if (h.Length is not (6 or 8)) return null;
            int B(int i) => int.Parse(h.Substring(i, 2), NumberStyles.HexNumber);
            return new Rgba((byte)B(0), (byte)B(2), (byte)B(4), h.Length == 8 ? (byte)B(6) : (byte)255);
        }

        // Legacy: three or four comma-separated values. Modern: three space-separated values, then "/ alpha".
        static (string[] parts, string alpha, bool legacy)? Split(string body)
        {
            if (body.Contains(','))
            {
                if (body.Contains('/')) return null;
                var p = body.Split(',');
                for (int i = 0; i < p.Length; i++) { p[i] = p[i].Trim(); if (p[i].Length == 0 || p[i].Contains(' ')) return null; }
                if (p.Length is not (3 or 4)) return null;
                return (p[..3], p.Length == 4 ? p[3] : null, true);
            }
            string alpha = null;
            var slash = body.IndexOf('/');
            if (slash >= 0) { alpha = body[(slash + 1)..].Trim(); body = body[..slash]; if (alpha.Length == 0) return null; }
            var parts = body.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != 3) return null;
            return (parts, alpha, false);
        }

        static double? Number(string t)
        {
            if (!double.TryParse(t, NumberStyles.Float, CultureInfo.InvariantCulture, out var v)) return null;
            return v;
        }

        static double? Alpha(string t)
        {
            if (t == null) return 1;
            double? v = t.EndsWith('%') ? Number(t[..^1]) / 100 : Number(t);
            return v == null ? null : Math.Clamp(v.Value, 0, 1);
        }

        static Rgba? Rgb(string[] p, string alphaText, bool legacy)
        {
            var ch = new double[3];
            for (int i = 0; i < 3; i++)
            {
                double? v = p[i].EndsWith('%') ? Number(p[i][..^1]) * 255 / 100 : Number(p[i]);
                if (v == null) return null;
                ch[i] = v.Value;
            }
            var a = Alpha(alphaText);
            if (a == null) return null;
            return new Rgba(Round(ch[0]), Round(ch[1]), Round(ch[2]), Round(a.Value * 255));
        }

        static Rgba? Hsl(string[] p, string alphaText, bool legacy)
        {
            double? h = Hue(p[0]);
            if (h == null || !p[1].EndsWith('%') || !p[2].EndsWith('%')) return null;
            double? s = Number(p[1][..^1]), l = Number(p[2][..^1]);
            var a = Alpha(alphaText);
            if (s == null || l == null || a == null) return null;
            double hue = ((h.Value % 360) + 360) % 360, sat = Math.Clamp(s.Value / 100, 0, 1), lig = Math.Clamp(l.Value / 100, 0, 1);
            double F(int n)
            {
                double k = (n + hue / 30) % 12, amp = sat * Math.Min(lig, 1 - lig);
                return lig - amp * Math.Max(-1, Math.Min(Math.Min(k - 3, 9 - k), 1));
            }
            return new Rgba(Round(F(0) * 255), Round(F(8) * 255), Round(F(4) * 255), Round(a.Value * 255));
        }

        static double? Hue(string t)
        {
            if (t.EndsWith("deg")) return Number(t[..^3]);
            if (t.EndsWith("turn")) return Number(t[..^4]) * 360;
            if (t.EndsWith("rad")) return Number(t[..^3]) * 180 / Math.PI;
            return Number(t);
        }
    }
}
