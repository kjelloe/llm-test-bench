using System;
using System.Collections.Generic;

namespace GameClient
{
    /// <summary>
    /// C# port of the Node server's js/statehash.js. The Unity client hashes its own copy
    /// of the authoritative state and compares with the hash the server publishes, so
    /// every function here must match the JavaScript byte for byte and value for value.
    /// </summary>
    public static class FixedMath
    {
        // JS: Math.floor(a / b) | 0 — exact in doubles for int32 operands, then wrapped to int32.
        public static int FloorDiv(int a, int b) => unchecked((int)(long)Math.Floor((double)a / b));

        public static int TruncDiv(int a, int b) => unchecked((int)(long)Math.Truncate((double)a / b));

        public static int SampleCellX(int world, int mapWidth)
        {
            int c = world >> 8;
            return (world & 255) == 0 && 2L * world > (long)mapWidth * 256 ? c - 1 : c;
        }
    }

    public sealed class ByteWriter
    {
        readonly List<byte> _bytes = new List<byte>();

        public ByteWriter U8(int v)
        {
            Check(v, 0, 0xff);
            _bytes.Add((byte)v);
            return this;
        }

        public ByteWriter U16(int v)
        {
            Check(v, 0, 0xffff);
            _bytes.Add((byte)v);
            _bytes.Add((byte)(v >> 8));
            return this;
        }

        public ByteWriter U32(long v)
        {
            Check(v, 0, 0xffffffffL);
            AddLe32((uint)v);
            return this;
        }

        public ByteWriter I32(long v)
        {
            Check(v, int.MinValue, int.MaxValue);
            AddLe32(unchecked((uint)(int)v));
            return this;
        }

        public ByteWriter Bool(bool v)
        {
            _bytes.Add(v ? (byte)1 : (byte)0);
            return this;
        }

        public ByteWriter OptU32(uint? v)
        {
            if (v == null) return U8(0);
            U8(1);
            return U32(v.Value);
        }

        public ByteWriter Str(string s)
        {
            if (s == null) throw new ArgumentNullException(nameof(s));
            var o = new List<byte>();
            for (int i = 0; i < s.Length; i++)
            {
                int code = s[i];
                if (char.IsHighSurrogate(s[i]) && i + 1 < s.Length && char.IsLowSurrogate(s[i + 1]))
                {
                    code = char.ConvertToUtf32(s[i], s[i + 1]);
                    i++;
                }
                if (code <= 0x7f) o.Add((byte)code);
                else if (code <= 0x7ff)
                {
                    o.Add((byte)(0xc0 | (code >> 6)));
                    o.Add((byte)(0x80 | (code & 0x3f)));
                }
                else if (code <= 0xffff)
                {
                    o.Add((byte)(0xe0 | (code >> 12)));
                    o.Add((byte)(0x80 | ((code >> 6) & 0x3f)));
                    o.Add((byte)(0x80 | (code & 0x3f)));
                }
                else
                {
                    o.Add((byte)(0xf0 | (code >> 18)));
                    o.Add((byte)(0x80 | ((code >> 12) & 0x3f)));
                    o.Add((byte)(0x80 | ((code >> 6) & 0x3f)));
                    o.Add((byte)(0x80 | (code & 0x3f)));
                }
            }
            U16(o.Count);
            _bytes.AddRange(o);
            return this;
        }

        public byte[] ToBytes() => _bytes.ToArray();

        void AddLe32(uint u)
        {
            _bytes.Add((byte)u);
            _bytes.Add((byte)(u >> 8));
            _bytes.Add((byte)(u >> 16));
            _bytes.Add((byte)(u >> 24));
        }

        static void Check(long v, long min, long max)
        {
            if (v < min || v > max) throw new ArgumentOutOfRangeException(nameof(v), v, "out of range");
        }
    }

    public static class StateHash
    {
        public static string Fnv1a64(byte[] bytes)
        {
            if (bytes == null) throw new ArgumentNullException(nameof(bytes));
            ulong h = 0xcbf29ce484222325UL;
            foreach (byte b in bytes)
            {
                h ^= b;
                h = unchecked(h * 0x100000001b3UL);
            }
            return h.ToString("x16");
        }

        public static byte[] StateBytes(GameState state)
        {
            if (state == null) throw new ArgumentNullException(nameof(state));
            var units = new List<UnitState>(state.Units);
            units.Sort((a, b) => a.Id.CompareTo(b.Id));
            var w = new ByteWriter().U32(state.Tick).U16(units.Count);
            foreach (UnitState u in units)
                w.U32(u.Id).U8(u.Team).I32(u.X).I32(u.Y).U8(u.Heading).U16(u.Hp).Bool(u.Alive).OptU32(u.Target).Str(u.Name);
            return w.ToBytes();
        }

        public static string HashState(GameState state) => Fnv1a64(StateBytes(state));
    }
}
