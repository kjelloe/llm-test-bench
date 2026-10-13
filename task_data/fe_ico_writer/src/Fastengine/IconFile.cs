using System;
using System.Collections.Generic;

namespace Fastengine
{
    // fastengine spec A14: the exe icon of a game whose icon is drawn in code, built on Linux without raylib or
    // any image library. The win-x64 publish passes the .ico as ApplicationIcon, so the PNGs end up inside the exe.
    public static class IconFile
    {
        // A PNG of width × height RGBA pixels (row by row, 4 bytes per pixel, top row first): signature, IHDR (8-bit
        // RGBA, no interlace), one or more IDAT chunks holding the zlib-compressed scanlines (each prefixed by its
        // filter type byte; any filter is fine), IEND. Every chunk carries its CRC-32. Width and height 1-256.
        public static byte[] Png(int width, int height, byte[] rgba) => throw new NotImplementedException();

        // An .ico holding the given PNGs as they are (Vista and later): ICONDIR (reserved 0, type 1, count), one
        // 16-byte ICONDIRENTRY per image in the order given (width and height bytes, where 0 means 256; colour count
        // 0; reserved 0; planes 1; bit count 32; the PNG's byte length; its offset from the start of the file), then
        // the PNGs back to back in the same order. Sizes are each PNG's own width and height, read from its IHDR.
        public static byte[] Ico(IReadOnlyList<byte[]> pngs) => throw new NotImplementedException();

        // The PNGs inside any file (an .ico, or an exe that embeds one): every place the PNG signature is followed by
        // an IHDR chunk, as (offset, width, height), in file order. A signature not followed by IHDR is not a PNG.
        public static List<(int Offset, int Width, int Height)> FindPngs(byte[] file) => throw new NotImplementedException();
    }
}
