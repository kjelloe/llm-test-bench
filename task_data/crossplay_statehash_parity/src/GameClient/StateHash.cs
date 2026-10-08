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
        public static int FloorDiv(int a, int b) => throw new NotImplementedException();
        public static int TruncDiv(int a, int b) => throw new NotImplementedException();
        public static int SampleCellX(int world, int mapWidth) => throw new NotImplementedException();
    }

    public sealed class ByteWriter
    {
        public ByteWriter U8(int v) => throw new NotImplementedException();
        public ByteWriter U16(int v) => throw new NotImplementedException();
        public ByteWriter U32(long v) => throw new NotImplementedException();
        public ByteWriter I32(long v) => throw new NotImplementedException();
        public ByteWriter Bool(bool v) => throw new NotImplementedException();
        public ByteWriter OptU32(uint? v) => throw new NotImplementedException();
        public ByteWriter Str(string s) => throw new NotImplementedException();
        public byte[] ToBytes() => throw new NotImplementedException();
    }

    public static class StateHash
    {
        public static string Fnv1a64(byte[] bytes) => throw new NotImplementedException();
        public static byte[] StateBytes(GameState state) => throw new NotImplementedException();
        public static string HashState(GameState state) => throw new NotImplementedException();
    }
}
