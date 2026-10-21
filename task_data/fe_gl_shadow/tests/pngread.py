"""8-bit RGB/RGBA PNG reader for the shot tests (from fastengine tools/palette.py, stdlib only)."""
import struct
import zlib
from collections import Counter


def read(path):
    """(width, height, [(r, g, b), ...]) top row first."""
    data = open(path, 'rb').read()
    pos, idat = 8, b''
    while pos < len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b'IHDR':
            width, height, depth, colour = struct.unpack('>IIBB', chunk[:10])
        elif kind == b'IDAT':
            idat += chunk
    if depth != 8 or colour not in (2, 6):
        raise ValueError(f'{path}: only 8-bit RGB/RGBA PNGs')
    bpp = 4 if colour == 6 else 3
    raw = zlib.decompress(idat)
    stride = width * bpp
    prev = bytearray(stride)
    out = []
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out.extend(tuple(line[i:i + 3]) for i in range(0, stride, bpp))
        prev = line
    return width, height, out
