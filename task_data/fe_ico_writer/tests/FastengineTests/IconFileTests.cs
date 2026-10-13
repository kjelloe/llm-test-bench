using System.Buffers.Binary;
using System.IO.Compression;
using Fastengine;
using Xunit;

namespace FastengineTests
{
    public class IconFileTests
    {
        static readonly byte[] Signature = { 137, 80, 78, 71, 13, 10, 26, 10 };

        static byte[] Pixels(int w, int h, int seed)
        {
            var r = new Random(seed);
            var p = new byte[w * h * 4];
            r.NextBytes(p);
            for (int i = 0; i < w * h; i++) if (i % 7 == 0) p[i * 4 + 3] = 0;
            return p;
        }

        static uint Crc32(byte[] data, int start, int count)
        {
            uint c = 0xFFFFFFFF;
            for (int i = start; i < start + count; i++)
            {
                c ^= data[i];
                for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320 & (uint)-(int)(c & 1));
            }
            return ~c;
        }

        // An independent PNG reader: chunk walk with CRC check, IHDR fields, all five scanline filters.
        static (int w, int h, byte[] rgba) Decode(byte[] png)
        {
            Assert.True(png.AsSpan(0, 8).SequenceEqual(Signature), "missing the PNG signature");
            int pos = 8, w = 0, h = 0;
            var idat = new MemoryStream();
            var types = new List<string>();
            while (pos < png.Length)
            {
                int len = BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(pos));
                var type = System.Text.Encoding.ASCII.GetString(png, pos + 4, 4);
                Assert.True(pos + 12 + len <= png.Length, $"chunk {type} runs past the end of the file");
                uint crc = BinaryPrimitives.ReadUInt32BigEndian(png.AsSpan(pos + 8 + len));
                Assert.True(crc == Crc32(png, pos + 4, 4 + len), $"chunk {type} has a wrong CRC");
                types.Add(type);
                if (type == "IHDR")
                {
                    w = BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(pos + 8));
                    h = BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(pos + 12));
                    Assert.Equal(new byte[] { 8, 6, 0, 0, 0 }, png.AsSpan(pos + 16, 5).ToArray());
                }
                if (type == "IDAT") idat.Write(png, pos + 8, len);
                pos += 12 + len;
            }
            Assert.Equal("IHDR", types[0]);
            Assert.Equal("IEND", types[^1]);
            Assert.Contains("IDAT", types);
            idat.Position = 0;
            var raw = new MemoryStream();
            using (var z = new ZLibStream(idat, CompressionMode.Decompress)) z.CopyTo(raw);
            var data = raw.ToArray();
            int stride = w * 4;
            Assert.True(data.Length == h * (stride + 1), $"{data.Length} bytes of scanlines, expected {h * (stride + 1)}");
            var outp = new byte[h * stride];
            for (int y = 0; y < h; y++)
            {
                int f = data[y * (stride + 1)];
                for (int x = 0; x < stride; x++)
                {
                    int a = x >= 4 ? outp[y * stride + x - 4] : 0, b = y > 0 ? outp[(y - 1) * stride + x] : 0;
                    int c = x >= 4 && y > 0 ? outp[(y - 1) * stride + x - 4] : 0;
                    int v = data[y * (stride + 1) + 1 + x];
                    int pa = Math.Abs(b - c), pb = Math.Abs(a - c), pc = Math.Abs(a + b - 2 * c);
                    int pred = f switch { 0 => 0, 1 => a, 2 => b, 3 => (a + b) / 2, 4 => pa <= pb && pa <= pc ? a : pb <= pc ? b : c, _ => throw new Exception($"filter type {f}") };
                    outp[y * stride + x] = (byte)(v + pred);
                }
            }
            return (w, h, outp);
        }

        [Theory]
        [InlineData(1, 1)]
        [InlineData(16, 16)]
        [InlineData(3, 5)]
        [InlineData(256, 256)]
        [InlineData(48, 20)]
        public void Png_DecodesBackToThePixels(int w, int h)
        {
            var px = Pixels(w, h, w * 1000 + h);
            var (dw, dh, back) = Decode(IconFile.Png(w, h, px));
            Assert.Equal((w, h), (dw, dh));
            Assert.True(px.SequenceEqual(back), "the decoded pixels differ from the input");
        }

        static byte[][] Set() => new[] { 16, 32, 48, 256 }.Select(s => IconFile.Png(s, s, Pixels(s, s, s))).ToArray();

        [Fact]
        public void Ico_HeaderAndEntries()
        {
            var pngs = Set().Append(IconFile.Png(20, 10, Pixels(20, 10, 9))).ToArray();
            var ico = IconFile.Ico(pngs);
            Assert.Equal(new byte[] { 0, 0, 1, 0, 5, 0 }, ico.AsSpan(0, 6).ToArray());
            int offset = 6 + 16 * pngs.Length;
            var sizes = new[] { (16, 16), (32, 32), (48, 48), (0, 0), (20, 10) };
            for (int i = 0; i < pngs.Length; i++)
            {
                var e = ico.AsSpan(6 + 16 * i, 16);
                Assert.True((e[0], e[1]) == sizes[i], $"entry {i}: width/height bytes {e[0]}x{e[1]}, expected {sizes[i]}");
                Assert.True(e[2] == 0 && e[3] == 0, $"entry {i}: colour count and reserved must be 0");
                Assert.True(BinaryPrimitives.ReadUInt16LittleEndian(e[4..]) == 1 && BinaryPrimitives.ReadUInt16LittleEndian(e[6..]) == 32, $"entry {i}: planes 1, bit count 32");
                Assert.Equal(pngs[i].Length, BinaryPrimitives.ReadInt32LittleEndian(e[8..]));
                Assert.Equal(offset, BinaryPrimitives.ReadInt32LittleEndian(e[12..]));
                Assert.True(ico.AsSpan(offset, pngs[i].Length).SequenceEqual(pngs[i]), $"entry {i}: the PNG bytes at its offset differ");
                offset += pngs[i].Length;
            }
            Assert.Equal(offset, ico.Length);
        }

        [Fact]
        public void FindPngs_InsideAnExe()
        {
            var ico = IconFile.Ico(Set());
            var exe = new MemoryStream();
            exe.Write(new byte[] { 0x4D, 0x5A, 0x90, 0 });
            exe.Write(new byte[300]);
            exe.Write(Signature); exe.Write(new byte[] { 0, 0, 0, 13, (byte)'t', (byte)'E', (byte)'X', (byte)'t' }); // a signature, then no IHDR
            exe.Write(new byte[17]);
            int icoAt = (int)exe.Length;
            exe.Write(ico);
            exe.Write(new byte[51]);
            var loose = IconFile.Png(7, 9, Pixels(7, 9, 1));
            int looseAt = (int)exe.Length;
            exe.Write(loose);
            exe.Write(Signature); exe.Write(new byte[] { 0, 0, 0, 13, (byte)'I', (byte)'H' }); // cut off at the end of the file
            var found = IconFile.FindPngs(exe.ToArray());
            var expected = new List<(int, int, int)>();
            int off = icoAt + 6 + 16 * 4;
            foreach (var (s, png) in new[] { 16, 32, 48, 256 }.Zip(Set())) { expected.Add((off, s, s)); off += png.Length; }
            expected.Add((looseAt, 7, 9));
            Assert.Equal(expected, found.Select(f => (f.Offset, f.Width, f.Height)).ToList());
        }

        [Fact]
        public void Png_RejectsWrongInput()
        {
            Assert.ThrowsAny<ArgumentException>(() => IconFile.Png(2, 2, new byte[15]));
            Assert.ThrowsAny<ArgumentException>(() => IconFile.Png(0, 4, new byte[0]));
            Assert.ThrowsAny<ArgumentException>(() => IconFile.Png(257, 1, new byte[257 * 4]));
        }
    }
}
