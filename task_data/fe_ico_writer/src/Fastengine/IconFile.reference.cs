using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

namespace Fastengine
{
    public static class IconFile
    {
        static readonly byte[] Signature = { 137, 80, 78, 71, 13, 10, 26, 10 };

        public static byte[] Png(int width, int height, byte[] rgba)
        {
            if (width < 1 || height < 1 || width > 256 || height > 256) throw new ArgumentOutOfRangeException(nameof(width));
            if (rgba == null || rgba.Length != width * height * 4) throw new ArgumentException("rgba must hold width * height * 4 bytes");
            using var ms = new MemoryStream();
            ms.Write(Signature);
            var ihdr = new byte[13];
            BinaryPrimitives.WriteInt32BigEndian(ihdr, width);
            BinaryPrimitives.WriteInt32BigEndian(ihdr.AsSpan(4), height);
            ihdr[8] = 8; ihdr[9] = 6;
            Chunk(ms, "IHDR", ihdr);
            using var raw = new MemoryStream();
            using (var z = new ZLibStream(raw, CompressionLevel.Optimal, leaveOpen: true))
                for (int y = 0; y < height; y++)
                {
                    z.WriteByte(0);
                    z.Write(rgba, y * width * 4, width * 4);
                }
            Chunk(ms, "IDAT", raw.ToArray());
            Chunk(ms, "IEND", Array.Empty<byte>());
            return ms.ToArray();
        }

        static void Chunk(Stream s, string type, byte[] data)
        {
            Span<byte> b = stackalloc byte[4];
            BinaryPrimitives.WriteInt32BigEndian(b, data.Length);
            s.Write(b);
            var t = System.Text.Encoding.ASCII.GetBytes(type);
            s.Write(t);
            s.Write(data);
            uint crc = Crc(Crc(0xFFFFFFFF, t), data) ^ 0xFFFFFFFF;
            BinaryPrimitives.WriteUInt32BigEndian(b, crc);
            s.Write(b);
        }

        static uint Crc(uint c, byte[] data)
        {
            foreach (var x in data)
            {
                c ^= x;
                for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320 ^ (c >> 1) : c >> 1;
            }
            return c;
        }

        public static byte[] Ico(IReadOnlyList<byte[]> pngs)
        {
            using var ms = new MemoryStream();
            using var w = new BinaryWriter(ms);
            w.Write((ushort)0);
            w.Write((ushort)1);
            w.Write((ushort)pngs.Count);
            var offset = 6 + 16 * pngs.Count;
            foreach (var png in pngs)
            {
                int width = BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(16)), height = BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(20));
                w.Write((byte)(width % 256));
                w.Write((byte)(height % 256));
                w.Write((byte)0);
                w.Write((byte)0);
                w.Write((ushort)1);
                w.Write((ushort)32);
                w.Write(png.Length);
                w.Write(offset);
                offset += png.Length;
            }
            foreach (var png in pngs) w.Write(png);
            return ms.ToArray();
        }

        public static List<(int Offset, int Width, int Height)> FindPngs(byte[] file)
        {
            var found = new List<(int, int, int)>();
            for (int i = 0; i + 24 <= file.Length; i++)
            {
                if (!file.AsSpan(i, 8).SequenceEqual(Signature)) continue;
                if (file[i + 12] != 'I' || file[i + 13] != 'H' || file[i + 14] != 'D' || file[i + 15] != 'R') continue;
                found.Add((i, BinaryPrimitives.ReadInt32BigEndian(file.AsSpan(i + 16)), BinaryPrimitives.ReadInt32BigEndian(file.AsSpan(i + 20))));
            }
            return found;
        }
    }
}
