using System;
using System.Collections.Generic;

namespace GameClient
{
    // QR codes for invite links: a port of the browser clients'
    // vendor/qrcode.mjs (Kazuhiko Arase, MIT) for the one path they use,
    // qrcode(0, 'M') + addData(text) in byte mode, versions 1-10 (up to 213
    // bytes). Same version choice, Reed-Solomon blocks, module placement and
    // mask scoring, so the matrix is identical. No UnityEngine, so tests can
    // compare it against the JS.
    public sealed class QrCode
    {
        const int Pad0 = 0xEC, Pad1 = 0x11, ModeByte = 1 << 2, LevelM = 0;

        // RS blocks for level M, versions 1-10: (count, total, data) groups.
        static readonly int[][] RsBlocksM =
        {
            new[] { 1, 26, 16 }, new[] { 1, 44, 28 }, new[] { 1, 70, 44 }, new[] { 2, 50, 32 },
            new[] { 2, 67, 43 }, new[] { 4, 43, 27 }, new[] { 4, 49, 31 }, new[] { 2, 60, 38, 2, 61, 39 },
            new[] { 3, 58, 36, 2, 59, 37 }, new[] { 4, 69, 43, 1, 70, 44 },
        };

        static readonly int[][] PatternPositions =
        {
            new int[0], new[] { 6, 18 }, new[] { 6, 22 }, new[] { 6, 26 }, new[] { 6, 30 },
            new[] { 6, 34 }, new[] { 6, 22, 38 }, new[] { 6, 24, 42 }, new[] { 6, 26, 46 }, new[] { 6, 28, 50 },
        };

        const int G15 = (1 << 10) | (1 << 8) | (1 << 5) | (1 << 4) | (1 << 2) | (1 << 1) | 1;
        const int G18 = (1 << 12) | (1 << 11) | (1 << 10) | (1 << 9) | (1 << 8) | (1 << 5) | (1 << 2) | 1;
        const int G15Mask = (1 << 14) | (1 << 12) | (1 << 10) | (1 << 4) | (1 << 1);

        static readonly int[] Exp = new int[256], Log = new int[256];

        static QrCode()
        {
            for (var i = 0; i < 8; i++) Exp[i] = 1 << i;
            for (var i = 8; i < 256; i++) Exp[i] = Exp[i - 4] ^ Exp[i - 5] ^ Exp[i - 6] ^ Exp[i - 8];
            for (var i = 0; i < 255; i++) Log[Exp[i]] = i;
        }

        public readonly int Version;
        public int ModuleCount => _count;

        readonly byte[] _bytes;
        readonly int _count;
        bool?[,] _modules;
        int[] _data;

        public QrCode(string text)
        {
            // qrcode.stringToBytes: each UTF-16 unit & 0xff (fine for URLs).
            _bytes = new byte[text.Length];
            for (var i = 0; i < text.Length; i++) _bytes[i] = (byte)(text[i] & 0xff);
            Version = 1;
            while (Version < 10 && DataBits(Version) > DataCount(Version) * 8) Version++;
            if (DataBits(Version) > DataCount(Version) * 8) throw new ArgumentException("text too long for a version 10 QR code");
            _count = Version * 4 + 17;
            var best = 0;
            var minLost = 0.0;
            for (var mask = 0; mask < 8; mask++)
            {
                Make(true, mask);
                var lost = LostPoint();
                if (mask == 0 || minLost > lost)
                {
                    minLost = lost;
                    best = mask;
                }
            }
            Make(false, best);
        }

        public bool IsDark(int row, int col) => _modules[row, col] == true;

        // getLengthInBits(MODE_8BIT_BYTE): 8 below version 10, 16 from it.
        static int LengthBits(int version) => version < 10 ? 8 : 16;

        int DataBits(int version) => 4 + LengthBits(version) + 8 * _bytes.Length;

        static int DataCount(int version)
        {
            var t = RsBlocksM[version - 1];
            var total = 0;
            for (var i = 0; i < t.Length; i += 3) total += t[i] * t[i + 2];
            return total;
        }

        void Make(bool test, int mask)
        {
            _modules = new bool?[_count, _count];
            ProbePattern(0, 0);
            ProbePattern(_count - 7, 0);
            ProbePattern(0, _count - 7);
            AdjustPatterns();
            TimingPatterns();
            TypeInfo(test, mask);
            if (Version >= 7) TypeNumber(test);
            _data ??= CreateData();
            MapData(mask);
        }

        void ProbePattern(int row, int col)
        {
            for (var r = -1; r <= 7; r++)
            {
                if (row + r <= -1 || _count <= row + r) continue;
                for (var c = -1; c <= 7; c++)
                {
                    if (col + c <= -1 || _count <= col + c) continue;
                    _modules[row + r, col + c] = (0 <= r && r <= 6 && (c == 0 || c == 6))
                        || (0 <= c && c <= 6 && (r == 0 || r == 6))
                        || (2 <= r && r <= 4 && 2 <= c && c <= 4);
                }
            }
        }

        void AdjustPatterns()
        {
            var pos = PatternPositions[Version - 1];
            foreach (var row in pos)
                foreach (var col in pos)
                {
                    if (_modules[row, col] != null) continue;
                    for (var r = -2; r <= 2; r++)
                        for (var c = -2; c <= 2; c++)
                            _modules[row + r, col + c] = r == -2 || r == 2 || c == -2 || c == 2 || (r == 0 && c == 0);
                }
        }

        void TimingPatterns()
        {
            for (var r = 8; r < _count - 8; r++)
                if (_modules[r, 6] == null) _modules[r, 6] = r % 2 == 0;
            for (var c = 8; c < _count - 8; c++)
                if (_modules[6, c] == null) _modules[6, c] = c % 2 == 0;
        }

        void TypeNumber(bool test)
        {
            var bits = BchTypeNumber(Version);
            for (var i = 0; i < 18; i++)
            {
                var mod = !test && ((bits >> i) & 1) == 1;
                _modules[i / 3, i % 3 + _count - 8 - 3] = mod;
                _modules[i % 3 + _count - 8 - 3, i / 3] = mod;
            }
        }

        void TypeInfo(bool test, int mask)
        {
            var bits = BchTypeInfo((LevelM << 3) | mask);
            for (var i = 0; i < 15; i++)
            {
                var mod = !test && ((bits >> i) & 1) == 1;
                if (i < 6) _modules[i, 8] = mod;
                else if (i < 8) _modules[i + 1, 8] = mod;
                else _modules[_count - 15 + i, 8] = mod;
            }
            for (var i = 0; i < 15; i++)
            {
                var mod = !test && ((bits >> i) & 1) == 1;
                if (i < 8) _modules[8, _count - i - 1] = mod;
                else if (i < 9) _modules[8, 15 - i - 1 + 1] = mod;
                else _modules[8, 15 - i - 1] = mod;
            }
            _modules[_count - 8, 8] = !test;
        }

        void MapData(int mask)
        {
            var inc = -1;
            var row = _count - 1;
            var bitIndex = 7;
            var byteIndex = 0;
            for (var col = _count - 1; col > 0; col -= 2)
            {
                if (col == 6) col -= 1;
                while (true)
                {
                    for (var c = 0; c < 2; c++)
                    {
                        if (_modules[row, col - c] != null) continue;
                        var dark = byteIndex < _data.Length && ((_data[byteIndex] >> bitIndex) & 1) == 1;
                        if (Mask(mask, row, col - c)) dark = !dark;
                        _modules[row, col - c] = dark;
                        if (--bitIndex == -1)
                        {
                            byteIndex++;
                            bitIndex = 7;
                        }
                    }
                    row += inc;
                    if (row < 0 || _count <= row)
                    {
                        row -= inc;
                        inc = -inc;
                        break;
                    }
                }
            }
        }

        static bool Mask(int pattern, int i, int j) => pattern switch
        {
            0 => (i + j) % 2 == 0,
            1 => i % 2 == 0,
            2 => j % 3 == 0,
            3 => (i + j) % 3 == 0,
            4 => (i / 2 + j / 3) % 2 == 0,
            5 => (i * j) % 2 + (i * j) % 3 == 0,
            6 => ((i * j) % 2 + (i * j) % 3) % 2 == 0,
            _ => ((i * j) % 3 + (i + j) % 2) % 2 == 0,
        };

        int[] CreateData()
        {
            var bits = new List<bool>();
            void Put(int num, int length)
            {
                for (var i = 0; i < length; i++) bits.Add(((num >> (length - i - 1)) & 1) == 1);
            }
            Put(ModeByte, 4);
            Put(_bytes.Length, LengthBits(Version));
            foreach (var b in _bytes) Put(b, 8);
            var totalData = DataCount(Version);
            if (bits.Count + 4 <= totalData * 8) Put(0, 4);
            while (bits.Count % 8 != 0) bits.Add(false);
            while (true)
            {
                if (bits.Count >= totalData * 8) break;
                Put(Pad0, 8);
                if (bits.Count >= totalData * 8) break;
                Put(Pad1, 8);
            }
            var buffer = new int[bits.Count / 8];
            for (var i = 0; i < bits.Count; i++)
                if (bits[i]) buffer[i / 8] |= 0x80 >> (i % 8);
            return CreateBytes(buffer);
        }

        int[] CreateBytes(int[] buffer)
        {
            var table = RsBlocksM[Version - 1];
            var blocks = new List<(int total, int data)>();
            for (var i = 0; i < table.Length; i += 3)
                for (var n = 0; n < table[i]; n++) blocks.Add((table[i + 1], table[i + 2]));
            var dc = new int[blocks.Count][];
            var ec = new int[blocks.Count][];
            int offset = 0, maxDc = 0, maxEc = 0, total = 0;
            for (var r = 0; r < blocks.Count; r++)
            {
                var dcCount = blocks[r].data;
                var ecCount = blocks[r].total - dcCount;
                maxDc = Math.Max(maxDc, dcCount);
                maxEc = Math.Max(maxEc, ecCount);
                total += blocks[r].total;
                dc[r] = new int[dcCount];
                Array.Copy(buffer, offset, dc[r], 0, dcCount);
                offset += dcCount;
                var rsPoly = ErrorCorrectPolynomial(ecCount);
                var raw = Poly(dc[r], rsPoly.Length - 1);
                var mod = PolyMod(raw, rsPoly);
                ec[r] = new int[rsPoly.Length - 1];
                for (var i = 0; i < ec[r].Length; i++)
                {
                    var modIndex = i + mod.Length - ec[r].Length;
                    ec[r][i] = modIndex >= 0 ? mod[modIndex] : 0;
                }
            }
            var data = new int[total];
            var index = 0;
            for (var i = 0; i < maxDc; i++)
                for (var r = 0; r < blocks.Count; r++)
                    if (i < dc[r].Length) data[index++] = dc[r][i];
            for (var i = 0; i < maxEc; i++)
                for (var r = 0; r < blocks.Count; r++)
                    if (i < ec[r].Length) data[index++] = ec[r][i];
            return data;
        }

        // qrPolynomial: leading zeros dropped, `shift` zeros appended.
        static int[] Poly(int[] num, int shift)
        {
            var offset = 0;
            while (offset < num.Length && num[offset] == 0) offset++;
            var result = new int[num.Length - offset + shift];
            Array.Copy(num, offset, result, 0, num.Length - offset);
            return result;
        }

        static int[] PolyMultiply(int[] a, int[] b)
        {
            var num = new int[a.Length + b.Length - 1];
            for (var i = 0; i < a.Length; i++)
                for (var j = 0; j < b.Length; j++)
                    num[i + j] ^= Gexp(Glog(a[i]) + Glog(b[j]));
            return Poly(num, 0);
        }

        static int[] PolyMod(int[] a, int[] e)
        {
            while (a.Length - e.Length >= 0)
            {
                var ratio = Glog(a[0]) - Glog(e[0]);
                var num = (int[])a.Clone();
                for (var i = 0; i < e.Length; i++) num[i] ^= Gexp(Glog(e[i]) + ratio);
                a = Poly(num, 0);
            }
            return a;
        }

        static int[] ErrorCorrectPolynomial(int length)
        {
            var a = new[] { 1 };
            for (var i = 0; i < length; i++) a = PolyMultiply(a, new[] { 1, Gexp(i) });
            return a;
        }

        static int Glog(int n) => n < 1 ? throw new ArgumentException($"glog({n})") : Log[n];

        static int Gexp(int n)
        {
            while (n < 0) n += 255;
            while (n >= 256) n -= 255;
            return Exp[n];
        }

        static int BchDigit(int data)
        {
            var digit = 0;
            for (var d = (uint)data; d != 0; d >>= 1) digit++;
            return digit;
        }

        static int BchTypeInfo(int data)
        {
            var d = data << 10;
            while (BchDigit(d) - BchDigit(G15) >= 0) d ^= G15 << (BchDigit(d) - BchDigit(G15));
            return ((data << 10) | d) ^ G15Mask;
        }

        static int BchTypeNumber(int data)
        {
            var d = data << 12;
            while (BchDigit(d) - BchDigit(G18) >= 0) d ^= G18 << (BchDigit(d) - BchDigit(G18));
            return (data << 12) | d;
        }

        double LostPoint()
        {
            var n = _count;
            var lost = 0.0;
            bool Dark(int r, int c) => _modules[r, c] == true;
            for (var row = 0; row < n; row++)
                for (var col = 0; col < n; col++)
                {
                    var same = 0;
                    var dark = Dark(row, col);
                    for (var r = -1; r <= 1; r++)
                    {
                        if (row + r < 0 || n <= row + r) continue;
                        for (var c = -1; c <= 1; c++)
                        {
                            if (col + c < 0 || n <= col + c || (r == 0 && c == 0)) continue;
                            if (dark == Dark(row + r, col + c)) same++;
                        }
                    }
                    if (same > 5) lost += 3 + same - 5;
                }
            for (var row = 0; row < n - 1; row++)
                for (var col = 0; col < n - 1; col++)
                {
                    var count = (Dark(row, col) ? 1 : 0) + (Dark(row + 1, col) ? 1 : 0) + (Dark(row, col + 1) ? 1 : 0) + (Dark(row + 1, col + 1) ? 1 : 0);
                    if (count == 0 || count == 4) lost += 3;
                }
            for (var row = 0; row < n; row++)
                for (var col = 0; col < n - 6; col++)
                    if (Dark(row, col) && !Dark(row, col + 1) && Dark(row, col + 2) && Dark(row, col + 3) && Dark(row, col + 4) && !Dark(row, col + 5) && Dark(row, col + 6))
                        lost += 40;
            for (var col = 0; col < n; col++)
                for (var row = 0; row < n - 6; row++)
                    if (Dark(row, col) && !Dark(row + 1, col) && Dark(row + 2, col) && Dark(row + 3, col) && Dark(row + 4, col) && !Dark(row + 5, col) && Dark(row + 6, col))
                        lost += 40;
            var darkCount = 0;
            for (var col = 0; col < n; col++)
                for (var row = 0; row < n; row++)
                    if (Dark(row, col)) darkCount++;
            return lost + Math.Abs(100.0 * darkCount / n / n - 50) / 5 * 10;
        }
    }
}
