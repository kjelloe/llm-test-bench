using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // A scripted RFC 6455 server on a loopback socket: each test plays one side of a real conversation.
    sealed class ScriptedServer : IDisposable
    {
        readonly TcpListener _listener = new TcpListener(IPAddress.Loopback, 0);
        public readonly Task Done;
        public Uri Uri(string pathAndQuery = "/ws?join=AB12") => new Uri($"ws://127.0.0.1:{((IPEndPoint)_listener.LocalEndpoint).Port}{pathAndQuery}");

        public ScriptedServer(Action<NetworkStream> script)
        {
            _listener.Start();
            Done = Task.Run(() =>
            {
                using TcpClient c = _listener.AcceptTcpClient();
                c.ReceiveTimeout = 5000;
                script(c.GetStream());
            });
        }

        public void Dispose() => _listener.Stop();

        public static string ReadRequest(Stream s)
        {
            var bytes = new List<byte>();
            while (bytes.Count < 4 || bytes[bytes.Count - 4] != '\r' || bytes[bytes.Count - 3] != '\n' || bytes[bytes.Count - 2] != '\r' || bytes[bytes.Count - 1] != '\n')
            {
                int b = s.ReadByte();
                if (b < 0) throw new IOException("client closed during handshake");
                bytes.Add((byte)b);
            }
            return Encoding.ASCII.GetString(bytes.ToArray());
        }

        public static string Header(string request, string name) =>
            request.Split("\r\n").Skip(1).Select(l => l.Split(':', 2)).Where(p => p.Length == 2 && p[0].Trim().Equals(name, StringComparison.OrdinalIgnoreCase)).Select(p => p[1].Trim()).FirstOrDefault();

        public static string Accept(string key)
        {
            using var sha1 = SHA1.Create();
            return Convert.ToBase64String(sha1.ComputeHash(Encoding.ASCII.GetBytes(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")));
        }

        public static byte[] Response(string accept) => Encoding.ASCII.GetBytes(
            $"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n");

        // Accepts the handshake; returns the client's request.
        public static string Handshake(Stream s, byte[] sendWithResponse = null)
        {
            string req = ReadRequest(s);
            byte[] resp = Response(Accept(Header(req, "Sec-WebSocket-Key")));
            if (sendWithResponse != null) resp = resp.Concat(sendWithResponse).ToArray();
            s.Write(resp, 0, resp.Length);
            return req;
        }

        // A server frame: never masked (RFC 6455 5.1).
        public static byte[] Frame(int opcode, byte[] payload, bool fin = true)
        {
            var f = new List<byte> { (byte)((fin ? 0x80 : 0) | opcode) };
            if (payload.Length < 126) f.Add((byte)payload.Length);
            else if (payload.Length <= 0xffff) { f.Add(126); f.Add((byte)(payload.Length >> 8)); f.Add((byte)payload.Length); }
            else { f.Add(127); for (int i = 7; i >= 0; i--) f.Add((byte)((long)payload.Length >> (8 * i))); }
            f.AddRange(payload);
            return f.ToArray();
        }

        public static byte[] Text(string t, bool fin = true, int opcode = 1) => Frame(opcode, Encoding.UTF8.GetBytes(t), fin);

        public static byte[] Exactly(Stream s, int n)
        {
            var b = new byte[n];
            for (int read = 0; read < n;)
            {
                int k = s.Read(b, read, n - read);
                if (k == 0) throw new IOException("client closed");
                read += k;
            }
            return b;
        }

        public sealed class ClientFrame { public bool Fin, Masked; public int Opcode; public byte[] Mask, Wire, Payload; }

        public static ClientFrame ReadClientFrame(Stream s)
        {
            byte[] h = Exactly(s, 2);
            var f = new ClientFrame { Fin = (h[0] & 0x80) != 0, Opcode = h[0] & 0x0f, Masked = (h[1] & 0x80) != 0 };
            long len = h[1] & 0x7f;
            if (len == 126) { byte[] b = Exactly(s, 2); len = (b[0] << 8) | b[1]; }
            else if (len == 127) { byte[] b = Exactly(s, 8); len = 0; for (int i = 0; i < 8; i++) len = (len << 8) | b[i]; }
            f.Mask = f.Masked ? Exactly(s, 4) : new byte[4];
            f.Wire = Exactly(s, (int)len);
            f.Payload = f.Wire.Select((b, i) => (byte)(b ^ f.Mask[i % 4])).ToArray();
            return f;
        }
    }

    public class WebSocketConnectionTests
    {
        static async Task Within(Task t) => Assert.True(await Task.WhenAny(t, Task.Delay(10000)) == t, "server script did not finish");

        static string Str(byte[] b) => b == null ? null : Encoding.UTF8.GetString(b);

        [Fact]
        public async Task Handshake_SendsAValidUpgradeRequest()
        {
            string req = null;
            using var server = new ScriptedServer(s => req = ScriptedServer.Handshake(s));
            using (new WebSocketConnection(server.Uri(), 1 << 20)) { }
            await Within(server.Done);
            string[] start = req.Split("\r\n")[0].Split(' ');
            Assert.Equal(new[] { "GET", "/ws?join=AB12", "HTTP/1.1" }, start);
            Assert.Equal(server.Uri().Authority, ScriptedServer.Header(req, "Host"));
            Assert.Equal("websocket", ScriptedServer.Header(req, "Upgrade"), StringComparer.OrdinalIgnoreCase);
            Assert.Contains("upgrade", ScriptedServer.Header(req, "Connection").ToLowerInvariant());
            Assert.Equal("13", ScriptedServer.Header(req, "Sec-WebSocket-Version"));
            Assert.Equal(16, Convert.FromBase64String(ScriptedServer.Header(req, "Sec-WebSocket-Key")).Length);
        }

        [Fact]
        public async Task Handshake_KeyIsFreshForEachConnection()
        {
            var keys = new List<string>();
            for (int i = 0; i < 2; i++)
            {
                using var server = new ScriptedServer(s => keys.Add(ScriptedServer.Header(ScriptedServer.Handshake(s), "Sec-WebSocket-Key")));
                using (new WebSocketConnection(server.Uri(), 1 << 20)) { }
                await Within(server.Done);
            }
            Assert.NotEqual(keys[0], keys[1]);
        }

        [Fact]
        public async Task Handshake_RejectsAWrongAccept()
        {
            using var server = new ScriptedServer(s =>
            {
                ScriptedServer.ReadRequest(s);
                byte[] r = ScriptedServer.Response(ScriptedServer.Accept("dGhlIHNhbXBsZSBub25jZQ=="));
                s.Write(r, 0, r.Length);
            });
            Assert.Throws<IOException>(() => new WebSocketConnection(server.Uri(), 1 << 20));
            await Within(server.Done);
        }

        [Fact]
        public async Task Handshake_RejectsANon101Answer()
        {
            using var server = new ScriptedServer(s =>
            {
                ScriptedServer.ReadRequest(s);
                byte[] r = Encoding.ASCII.GetBytes("HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n");
                s.Write(r, 0, r.Length);
            });
            Assert.Throws<IOException>(() => new WebSocketConnection(server.Uri(), 1 << 20));
            await Within(server.Done);
        }

        [Fact]
        public async Task FirstFrame_InTheSameSegmentAsThe101_IsNotLost()
        {
            // Servers often write the 101 and the welcome message back to back; a buffered header
            // reader that reads past the blank line swallows the start of the first frame.
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s, ScriptedServer.Text("{\"type\":\"welcome\"}")); ScriptedServer.Exactly(s, 1); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Assert.Equal("{\"type\":\"welcome\"}", Str(ws.ReadMessage(out string reason)));
            Assert.Null(reason);
            ws.Abort();
            await Task.WhenAny(server.Done, Task.Delay(2000));
        }

        [Theory]
        [InlineData(5)]
        [InlineData(125)]
        [InlineData(126)]
        [InlineData(300)]
        [InlineData(65535)]
        [InlineData(70000)]
        public async Task SendText_FramesAreFinalTextMaskedWithTheRightLength(int size)
        {
            string text = new string('é', size / 2) + new string('x', size % 2);
            ScriptedServer.ClientFrame f = null;
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); f = ScriptedServer.ReadClientFrame(s); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            ws.SendText(text);
            await Within(server.Done);
            Assert.True(f.Fin);
            Assert.Equal(1, f.Opcode);
            Assert.True(f.Masked, "client frames must be masked");
            Assert.Equal(Encoding.UTF8.GetByteCount(text), f.Wire.Length);
            Assert.Equal(text, Str(f.Payload));
        }

        [Fact]
        public async Task SendText_UsesAFreshMaskPerFrame()
        {
            var masks = new List<string>();
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); for (int i = 0; i < 4; i++) masks.Add(Convert.ToBase64String(ScriptedServer.ReadClientFrame(s).Mask)); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            for (int i = 0; i < 4; i++) ws.SendText("move " + i);
            await Within(server.Done);
            Assert.True(masks.Distinct().Count() > 1, "every frame used the same mask");
            Assert.DoesNotContain(Convert.ToBase64String(new byte[4]), masks);
        }

        [Theory]
        [InlineData(10)]
        [InlineData(126)]
        [InlineData(1000)]
        [InlineData(65536)]
        [InlineData(200000)]
        public async Task ReadMessage_DecodesEveryLengthForm(int size)
        {
            string text = string.Concat(Enumerable.Range(0, size).Select(i => (char)('a' + i % 26)));
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); byte[] f = ScriptedServer.Text(text); s.Write(f, 0, f.Length); ScriptedServer.Exactly(s, 1); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Assert.Equal(text, Str(ws.ReadMessage(out _)));
            ws.Abort();
            await Task.WhenAny(server.Done, Task.Delay(2000));
        }

        [Fact]
        public async Task ReadMessage_JoinsFragments_AndAnswersAPingBetweenThem()
        {
            ScriptedServer.ClientFrame pong = null;
            using var server = new ScriptedServer(s =>
            {
                ScriptedServer.Handshake(s);
                foreach (byte[] f in new[] { ScriptedServer.Text("{\"tick\":", fin: false), ScriptedServer.Frame(9, Encoding.ASCII.GetBytes("hb-7")), ScriptedServer.Text("42", fin: false, opcode: 0), ScriptedServer.Text("}", opcode: 0), ScriptedServer.Text("next") })
                    s.Write(f, 0, f.Length);
                pong = ScriptedServer.ReadClientFrame(s);
                ScriptedServer.Exactly(s, 1);
            });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Assert.Equal("{\"tick\":42}", Str(ws.ReadMessage(out _)));
            Assert.Equal("next", Str(ws.ReadMessage(out _)));
            ws.Abort();
            await Within(server.Done);
            Assert.Equal(0xA, pong.Opcode);
            Assert.True(pong.Masked);
            Assert.Equal("hb-7", Str(pong.Payload));
        }

        [Fact]
        public async Task ReadMessage_IgnoresAnUnsolicitedPong()
        {
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); foreach (byte[] f in new[] { ScriptedServer.Frame(0xA, new byte[0]), ScriptedServer.Text("ok") }) s.Write(f, 0, f.Length); ScriptedServer.Exactly(s, 1); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Assert.Equal("ok", Str(ws.ReadMessage(out _)));
            ws.Abort();
            await Task.WhenAny(server.Done, Task.Delay(2000));
        }

        [Fact]
        public async Task ServerClose_ReturnsNull_ReportsCodeAndReason_AndEchoesTheClose()
        {
            ScriptedServer.ClientFrame echo = null;
            byte[] payload = new byte[] { 0x0F, 0xA0 }.Concat(Encoding.UTF8.GetBytes("seat taken")).ToArray(); // 4000
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); byte[] f = ScriptedServer.Frame(8, payload); s.Write(f, 0, f.Length); echo = ScriptedServer.ReadClientFrame(s); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Assert.Null(ws.ReadMessage(out string reason));
            Assert.Equal("4000 seat taken", reason);
            await Within(server.Done);
            Assert.Equal(8, echo.Opcode);
            Assert.True(echo.Masked);
            Assert.Equal(4000, (echo.Payload[0] << 8) | echo.Payload[1]);
        }

        [Fact]
        public async Task ServerClose_WithoutACode_Reports1005()
        {
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); byte[] f = ScriptedServer.Frame(8, new byte[0]); s.Write(f, 0, f.Length); try { ScriptedServer.ReadClientFrame(s); } catch (IOException) { } });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Assert.Null(ws.ReadMessage(out string reason));
            Assert.Equal("1005", reason);
            await Within(server.Done);
        }

        [Fact]
        public async Task OversizedMessage_Throws_EvenWhenFragmented()
        {
            using var server = new ScriptedServer(s =>
            {
                ScriptedServer.Handshake(s);
                foreach (byte[] f in new[] { ScriptedServer.Text(new string('a', 600), fin: false), ScriptedServer.Text(new string('b', 600), opcode: 0) })
                    s.Write(f, 0, f.Length);
                try { ScriptedServer.Exactly(s, 1); } catch (IOException) { }
            });
            using var ws = new WebSocketConnection(server.Uri(), 1000);
            Assert.Throws<IOException>(() => ws.ReadMessage(out _));
            ws.Abort();
            await Task.WhenAny(server.Done, Task.Delay(2000));
        }

        [Fact]
        public async Task ConnectionDroppedMidFrame_ThrowsIOException()
        {
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); byte[] f = ScriptedServer.Text("truncated message"); s.Write(f, 0, 6); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            await Within(server.Done);
            Assert.Throws<IOException>(() => ws.ReadMessage(out _));
        }

        [Fact]
        public async Task Abort_UnblocksAReaderOnAnotherThread()
        {
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); try { ScriptedServer.Exactly(s, 1); } catch (IOException) { } });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            Task<Exception> reader = Task.Run(() => { try { ws.ReadMessage(out _); return null; } catch (Exception e) { return e; } });
            await Task.Delay(200);
            ws.Abort();
            Assert.True(await Task.WhenAny(reader, Task.Delay(5000)) == reader, "reader still blocked after Abort");
            Assert.NotNull(reader.Result);
        }

        [Fact]
        public async Task ConcurrentSends_NeverInterleaveFrames()
        {
            const int perThread = 200;
            var got = new List<string>();
            using var server = new ScriptedServer(s => { ScriptedServer.Handshake(s); for (int i = 0; i < 2 * perThread; i++) got.Add(Str(ScriptedServer.ReadClientFrame(s).Payload)); });
            using var ws = new WebSocketConnection(server.Uri(), 1 << 20);
            await Task.WhenAll(
                Task.Run(() => { for (int i = 0; i < perThread; i++) ws.SendText("A" + i + new string('a', 300)); }),
                Task.Run(() => { for (int i = 0; i < perThread; i++) ws.SendText("B" + i + new string('b', 300)); }));
            await Within(server.Done);
            Assert.Equal(Enumerable.Range(0, perThread).Select(i => "A" + i + new string('a', 300)), got.Where(m => m[0] == 'A'));
            Assert.Equal(Enumerable.Range(0, perThread).Select(i => "B" + i + new string('b', 300)), got.Where(m => m[0] == 'B'));
        }
    }
}
