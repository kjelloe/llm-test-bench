using System;

namespace GameClient
{
    // QR codes for invite links: a port of the browser clients' vendor/qrcode.mjs (Kazuhiko Arase, MIT)
    // for the one path they use, qrcode(0, 'M') + addData(text) + make(): byte mode, error correction
    // level M, versions 1-10. No UnityEngine, so it can be tested against the JS.
    public sealed class QrCode
    {
        // Encodes text (each UTF-16 unit's low byte, as qrcode.stringToBytes does) in the smallest version
        // that fits; throws ArgumentException when version 10 is not enough.
        public QrCode(string text) => throw new NotImplementedException();

        public int Version => throw new NotImplementedException();
        public int ModuleCount => throw new NotImplementedException();   // Version * 4 + 17
        public bool IsDark(int row, int col) => throw new NotImplementedException();
    }
}
