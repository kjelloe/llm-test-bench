using System;
using System.IO;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;

namespace GameClient
{
    // A minimal RFC 6455 client on blocking socket I/O: handshake, masked
    // client frames, fragmented messages, ping/pong, close; ws:// and wss://.
    // It exists because the Linux players' async socket I/O (ClientWebSocket)
    // stops delivering reads for seconds at a time once a write is in flight
    // on the same socket; blocking reads on their own thread do not. One
    // thread may read while another writes.
    public sealed class WebSocketConnection : IDisposable
    {
        const string Guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

        readonly TcpClient _tcp;
        readonly Stream _stream;
        readonly object _writeLock = new object();
        readonly RandomNumberGenerator _random = RandomNumberGenerator.Create();
        readonly int _maxMessageBytes;

        public WebSocketConnection(Uri uri, int maxMessageBytes)
        {
            _maxMessageBytes = maxMessageBytes;
            var secure = uri.Scheme == "wss";
            var port = uri.IsDefaultPort ? (secure ? 443 : 80) : uri.Port;
            _tcp = new TcpClient { NoDelay = true };
            _tcp.Connect(uri.Host, port);
            Stream stream = _tcp.GetStream();
            if (secure)
            {
                var ssl = new SslStream(stream);
                ssl.AuthenticateAsClient(uri.Host);
                stream = ssl;
            }
            _stream = stream;
            Handshake(uri, port);
        }

        void Handshake(Uri uri, int port)
        {
            var key = Convert.ToBase64String(RandomBytes(16));
            var host = uri.IsDefaultPort ? uri.Host : $"{uri.Host}:{port}";
            var request = $"GET {uri.PathAndQuery} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n" +
                          $"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n";
            Write(Encoding.ASCII.GetBytes(request));

            var headers = ReadHeaders();
            var status = headers.Split(new[] { "\r\n" }, StringSplitOptions.None)[0];
            if (!status.Contains(" 101 ")) throw new IOException($"handshake refused: {status}");
            using var sha1 = SHA1.Create();
            var accept = Convert.ToBase64String(sha1.ComputeHash(Encoding.ASCII.GetBytes(key + Guid)));
            if (headers.IndexOf($"Sec-WebSocket-Accept: {accept}", StringComparison.OrdinalIgnoreCase) < 0)
                throw new IOException("handshake: bad Sec-WebSocket-Accept");
        }

        string ReadHeaders()
        {
            var bytes = new MemoryStream();
            while (true)
            {
                var b = _stream.ReadByte();
                if (b < 0) throw new IOException("closed during handshake");
                bytes.WriteByte((byte)b);
                var n = (int)bytes.Length;
                var buffer = bytes.GetBuffer();
                if (n >= 4 && buffer[n - 4] == '\r' && buffer[n - 3] == '\n' && buffer[n - 2] == '\r' && buffer[n - 1] == '\n')
                    return Encoding.ASCII.GetString(buffer, 0, n);
                if (n > 16 * 1024) throw new IOException("handshake headers too long");
            }
        }

        // Blocks until a whole text or binary message arrives (answering pings
        // on the way). Returns null when the server closes; closeReason says why.
        public byte[] ReadMessage(out string closeReason)
        {
            closeReason = null;
            var message = new MemoryStream();
            while (true)
            {
                var head = ReadExactly(2);
                var fin = (head[0] & 0x80) != 0;
                var opcode = head[0] & 0x0f;
                long length = head[1] & 0x7f;
                if (length == 126)
                {
                    var b = ReadExactly(2);
                    length = (b[0] << 8) | b[1];
                }
                else if (length == 127)
                {
                    var b = ReadExactly(8);
                    length = 0;
                    for (var i = 0; i < 8; i++) length = (length << 8) | b[i];
                }
                var mask = (head[1] & 0x80) != 0 ? ReadExactly(4) : null;
                if (message.Length + length > _maxMessageBytes) throw new IOException("message exceeded limit");
                var payload = ReadExactly((int)length);
                if (mask != null)
                    for (var i = 0; i < payload.Length; i++) payload[i] ^= mask[i % 4];

                switch (opcode)
                {
                    case 0x8: // close: echo it, report the code and reason
                        var code = payload.Length >= 2 ? (payload[0] << 8) | payload[1] : 1005;
                        var reason = payload.Length > 2 ? Encoding.UTF8.GetString(payload, 2, payload.Length - 2) : "";
                        closeReason = $"{code} {reason}".Trim();
                        try { WriteFrame(0x8, payload); } catch (IOException) { }
                        return null;
                    case 0x9: // ping
                        WriteFrame(0xA, payload);
                        continue;
                    case 0xA: // pong
                        continue;
                }
                message.Write(payload, 0, payload.Length);
                if (fin) return message.ToArray();
            }
        }

        public void SendText(string text) => WriteFrame(0x1, Encoding.UTF8.GetBytes(text));

        // Kills the socket without a close handshake (a network drop).
        public void Abort() => _tcp.Close();

        public void Dispose()
        {
            _tcp.Close();
            _random.Dispose();
        }

        void WriteFrame(int opcode, byte[] payload)
        {
            var frame = new MemoryStream();
            frame.WriteByte((byte)(0x80 | opcode));
            if (payload.Length < 126) frame.WriteByte((byte)(0x80 | payload.Length));
            else if (payload.Length <= 0xffff)
            {
                frame.WriteByte(0x80 | 126);
                frame.WriteByte((byte)(payload.Length >> 8));
                frame.WriteByte((byte)payload.Length);
            }
            else
            {
                frame.WriteByte(0x80 | 127);
                for (var i = 7; i >= 0; i--) frame.WriteByte((byte)((long)payload.Length >> (8 * i)));
            }
            var mask = RandomBytes(4);
            frame.Write(mask, 0, 4);
            for (var i = 0; i < payload.Length; i++) frame.WriteByte((byte)(payload[i] ^ mask[i % 4]));
            Write(frame.ToArray());
        }

        void Write(byte[] bytes)
        {
            lock (_writeLock)
            {
                _stream.Write(bytes, 0, bytes.Length);
                _stream.Flush();
            }
        }

        byte[] ReadExactly(int count)
        {
            var buffer = new byte[count];
            var read = 0;
            while (read < count)
            {
                var n = _stream.Read(buffer, read, count - read);
                if (n == 0) throw new IOException("connection closed");
                read += n;
            }
            return buffer;
        }

        byte[] RandomBytes(int count)
        {
            var bytes = new byte[count];
            lock (_random) _random.GetBytes(bytes);
            return bytes;
        }
    }
}
