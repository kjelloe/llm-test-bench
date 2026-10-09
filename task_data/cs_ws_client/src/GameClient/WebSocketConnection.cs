using System;
using System.IO;

namespace GameClient
{
    // A minimal RFC 6455 client on blocking socket I/O (TcpClient; SslStream for wss://).
    // One thread reads with ReadMessage while another may call SendText.
    public sealed class WebSocketConnection : IDisposable
    {
        // Connects and completes the opening handshake; throws IOException if the server refuses
        // or answers with a wrong Sec-WebSocket-Accept.
        public WebSocketConnection(Uri uri, int maxMessageBytes) => throw new NotImplementedException();

        // Blocks until a whole text or binary message arrives (answering pings on the way).
        // Returns null when the server closes; closeReason is then "<code> <reason>" trimmed,
        // or "1005" when the close frame carries no code.
        public byte[] ReadMessage(out string closeReason) => throw new NotImplementedException();

        public void SendText(string text) => throw new NotImplementedException();

        // Kills the socket without a close handshake (a network drop).
        public void Abort() => throw new NotImplementedException();

        public void Dispose() => throw new NotImplementedException();
    }
}
