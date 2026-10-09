using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // Each test starts the real Node authority (tests/server.mjs) on a free port and drives a SeatClient
    // against it. The server is told to drop or supersede a seat through its stdin.
    public sealed class NodeServer : IDisposable
    {
        readonly Process _node;
        readonly BlockingCollection<string> _lines = new BlockingCollection<string>();
        public readonly int Port;

        public NodeServer()
        {
            string dir = AppContext.BaseDirectory;
            while (dir != null && !File.Exists(Path.Combine(dir, "tests", "server.mjs"))) dir = Path.GetDirectoryName(dir);
            Assert.True(dir != null, "tests/server.mjs not found above the test binaries");
            _node = Process.Start(new ProcessStartInfo("node", Path.Combine(dir, "tests", "server.mjs"))
            {
                RedirectStandardInput = true, RedirectStandardOutput = true, UseShellExecute = false,
            });
            _node.OutputDataReceived += (_, e) => { if (e.Data != null) _lines.Add(e.Data); };
            _node.BeginOutputReadLine();
            Assert.True(_lines.TryTake(out string first, 10000) && first.StartsWith("port "), "server did not start");
            Port = int.Parse(first.Substring(5));
        }

        public string Url => $"ws://127.0.0.1:{Port}/ws?join=AB12";

        public void Control(string line) { _node.StandardInput.WriteLine(line); _node.StandardInput.Flush(); }

        public JsonElement Query(string what, int team)
        {
            Control($"{what} {team}");
            while (_lines.TryTake(out string line, 5000))
                if (line.StartsWith($"{what} {team} ")) return JsonDocument.Parse(line.Substring(what.Length + team.ToString().Length + 2)).RootElement;
            throw new TimeoutException($"no answer to {what} {team}");
        }

        public int[] Received(int team) => Query("log", team).EnumerateArray().Select(e => e.GetInt32()).ToArray();
        public bool[] Reclaimed(int team) => Query("welcomes", team).EnumerateArray().Select(e => e.GetProperty("reclaimed").GetBoolean()).ToArray();

        public void Dispose()
        {
            try { _node.StandardInput.Close(); if (!_node.WaitForExit(3000)) _node.Kill(); } catch (InvalidOperationException) { }
        }
    }

    public class RoundTripTests
    {
        static void WaitFor(Func<bool> condition, string what, int ms = 8000)
        {
            var sw = Stopwatch.StartNew();
            while (!condition())
            {
                Assert.True(sw.ElapsedMilliseconds < ms, $"timed out waiting for: {what}");
                Thread.Sleep(20);
            }
        }

        [Fact]
        public void Connects_GetsASeat_AndCommandsArriveInOrder()
        {
            using var server = new NodeServer();
            using var client = new SeatClient(server.Url);
            client.Start();
            WaitFor(() => client.Connected, "welcome");
            Assert.Equal(0, client.Team);
            for (int i = 0; i < 20; i++) Assert.Equal(i + 1, client.SendCommand($"{{\"helm\":{i}}}"));
            WaitFor(() => client.AckedSeq == 20, "20 acks");
            Assert.Equal(Enumerable.Range(1, 20), server.Received(0));
        }

        [Fact]
        public void CommandsSentBeforeTheWelcome_AreDeliveredAfterIt()
        {
            using var server = new NodeServer();
            using var client = new SeatClient(server.Url);
            client.SendCommand("\"early\"");
            client.Start();
            client.SendCommand("\"second\"");
            WaitFor(() => client.AckedSeq == 2, "both acked");
            Assert.Equal(new[] { 1, 2 }, server.Received(0));
        }

        [Fact]
        public void ANetworkDrop_ReconnectsWithTheToken_AndReclaimsTheSameSeat()
        {
            using var server = new NodeServer();
            using var other = new SeatClient(server.Url);   // takes team 0
            other.Start();
            WaitFor(() => other.Connected, "first client welcomed");
            using var client = new SeatClient(server.Url);
            client.Start();
            WaitFor(() => client.Connected, "second client welcomed");
            Assert.Equal(1, client.Team);
            server.Control("drop 1");
            WaitFor(() => client.Welcomes == 2 && client.Connected, "reconnect");
            Assert.Equal(1, client.Team);
            Assert.Equal(new[] { false, true }, server.Reclaimed(1));
        }

        [Fact]
        public void CommandsDuringADrop_ArriveOnceAndInOrder_AckedOnesAreNotResent()
        {
            using var server = new NodeServer();
            using var client = new SeatClient(server.Url);
            client.Start();
            WaitFor(() => client.Connected, "welcome");
            for (int i = 1; i <= 5; i++) client.SendCommand(i.ToString());
            WaitFor(() => client.AckedSeq == 5, "first five acked");
            server.Control("drop 0");
            WaitFor(() => !client.Connected, "drop noticed");
            for (int i = 6; i <= 9; i++) client.SendCommand(i.ToString());
            WaitFor(() => client.AckedSeq == 9, "queued commands acked after reconnect");
            client.SendCommand("10");
            WaitFor(() => client.AckedSeq == 10, "a new command after reconnect");
            Assert.Equal(Enumerable.Range(1, 10), server.Received(0));
        }

        [Fact]
        public void ClosedWith4000_IsSuperseded_AndNeverReconnects()
        {
            using var server = new NodeServer();
            using var client = new SeatClient(server.Url);
            client.Start();
            WaitFor(() => client.Connected, "welcome");
            server.Control("supersede 0");
            WaitFor(() => client.Superseded, "superseded");
            Thread.Sleep(2500); // longer than the first reconnect delay
            Assert.False(client.Connected);
            Assert.Equal(1, client.Welcomes);
            Assert.Single(server.Reclaimed(0));
        }

        [Fact]
        public void ServerNotRunningYet_KeepsRetrying_ThenConnects()
        {
            int port;
            using (var probe = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0))
            {
                probe.Start();
                port = ((System.Net.IPEndPoint)probe.LocalEndpoint).Port;
            }
            using var client = new SeatClient($"ws://127.0.0.1:{port}/ws");
            client.Start();
            Thread.Sleep(1500);
            Assert.False(client.Connected);
            using var server = new NodeServer();
            using var late = new SeatClient(server.Url);
            late.Start();
            WaitFor(() => late.Connected, "a client started after the server connects");
        }

        [Fact]
        public void Dispose_StopsTheClient_AndTheServerSeesTheSocketGo()
        {
            using var server = new NodeServer();
            var client = new SeatClient(server.Url);
            client.Start();
            WaitFor(() => client.Connected, "welcome");
            var sw = Stopwatch.StartNew();
            client.Dispose();
            Assert.True(sw.ElapsedMilliseconds < 3000, $"Dispose took {sw.ElapsedMilliseconds} ms");
            Assert.False(client.Connected);
            Thread.Sleep(1500);
            Assert.Single(server.Reclaimed(0)); // no reconnect after Dispose
        }
    }
}
