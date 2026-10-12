using System.Diagnostics;
using System.Net.Http;
using System.Text.RegularExpressions;
using Fastengine;
using Xunit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace FastengineTests
{
    // Runs the real guard (solo/guard.cjs) and a stand-in game server (solo/game/server/server.js) under node.
    public sealed class SoloServerTests : IDisposable
    {
        readonly string _solo, _state;
        readonly int _logStart = Log.Snapshot().Length;
        readonly List<IDisposable> _cleanup = new();
        readonly List<int> _pids = new();

        public SoloServerTests()
        {
            var dir = AppContext.BaseDirectory;
            while (dir != null && !File.Exists(Path.Combine(dir, "solo", "solo.json"))) dir = Path.GetDirectoryName(dir);
            Assert.True(dir != null, "solo/solo.json not found above the test binaries");
            _solo = Path.Combine(dir, "solo");
            _state = Path.Combine(Path.GetTempPath(), "fe-solo-" + Guid.NewGuid().ToString("N"));
        }

        public void Dispose()
        {
            foreach (var d in _cleanup) d.Dispose();
            foreach (var pid in _pids)   // whatever the implementation did, leave no server behind
                try { Process.GetProcessById(pid).Kill(entireProcessTree: true); } catch (ArgumentException) { } catch (InvalidOperationException) { }
            try { Directory.Delete(_state, true); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }

        SoloServer New()
        {
            var s = new SoloServer(_solo);
            _cleanup.Add(s);
            return s;
        }

        static void PumpUntil(SoloServer s, Func<bool> done, string what, int ms = 15000)
        {
            var sw = Stopwatch.StartNew();
            while (!done())
            {
                Assert.True(sw.ElapsedMilliseconds < ms, $"timed out waiting for {what}");
                s.Pump();
                Thread.Sleep(20);
            }
        }

        string[] Logged() => Log.Snapshot().Skip(_logStart).ToArray();

        static bool Gone(int pid)
        {
            try { return Process.GetProcessById(pid).HasExited; }
            catch (ArgumentException) { return true; }
        }

        (SoloServer server, string url) StartReady(Dictionary<string, string> env = null)
        {
            var s = New();
            string url = null;
            s.Ready += u => url = u;
            s.Start(_state, env);
            if (s.Pid is int pid) _pids.Add(pid);
            PumpUntil(s, () => url != null, "Ready");
            return (s, url);
        }

        [Fact]
        public void Ready_GivesTheSocketUrl_AndTheServerAnswersThere()
        {
            var s = New();
            var urls = new List<string>();
            int thread = -1;
            s.Ready += u => { urls.Add(u); thread = Environment.CurrentManagedThreadId; };
            s.Start(_state);
            if (s.Pid is int pid) _pids.Add(pid);
            PumpUntil(s, () => urls.Count > 0, "Ready");
            for (int i = 0; i < 20; i++) { s.Pump(); Thread.Sleep(25); }
            Assert.Single(urls);   // the server announces twice; Ready once
            Assert.Equal(Environment.CurrentManagedThreadId, thread);
            var m = Regex.Match(urls[0], @"^ws://127\.0\.0\.1:(\d+)/ws$");
            Assert.True(m.Success, $"bad url {urls[0]}");
            using var http = new HttpClient();
            Assert.Equal("ok", http.GetStringAsync($"http://127.0.0.1:{m.Groups[1].Value}/").Result);
        }

        [Fact]
        public void ServerOutput_IsLogged_WithItsEnvironment()
        {
            StartReady();
            var lines = Logged();
            Assert.Contains(lines, l => Regex.IsMatch(l, @"^\[Server\] serving on http://localhost:\d+$"));
            var want = $"[Server] env MODE=solo SAVE={_state}/autosave.json STATE_DIR={_state}";
            Assert.True(lines.Contains(want), $"no '{want}' in the log:\n" + string.Join("\n", lines));
        }

        [Fact]
        public void LaunchEnv_OverridesSoloJson_WithTheStateFolder()
        {
            StartReady(new Dictionary<string, string> { ["MODE"] = "resume:{state}" });
            Assert.Contains(Logged(), l => l.StartsWith($"[Server] env MODE=resume:{_state} "));
        }

        [Fact]
        public void Dispose_LetsTheServerSave()
        {
            var (s, _) = StartReady();
            int pid = s.Pid.Value;
            var sw = Stopwatch.StartNew();
            s.Dispose();
            Assert.True(sw.ElapsedMilliseconds < 3500, $"Dispose took {sw.ElapsedMilliseconds} ms");
            Assert.True(File.Exists(Path.Combine(_state, "autosave.json")), "the server did not save: it was killed, or its stdin never closed");
            Assert.True(Gone(pid), "the server is still running");
        }

        [Fact]
        public void Dispose_KillsAServerThatWillNotStop()
        {
            var (s, _) = StartReady(new Dictionary<string, string> { ["STUBBORN"] = "1" });
            int pid = s.Pid.Value;
            var sw = Stopwatch.StartNew();
            s.Dispose();
            var waitGone = Stopwatch.StartNew();
            while (!Gone(pid) && waitGone.ElapsedMilliseconds < 3000) Thread.Sleep(50);
            Assert.True(Gone(pid), "a server that ignores SIGTERM is still running after Dispose");
            Assert.True(sw.ElapsedMilliseconds < 8000, $"Dispose took {sw.ElapsedMilliseconds} ms");
        }

        [Fact]
        public void AServerThatExits_RaisesFailed_OnlyFromPump()
        {
            var s = New();
            var failed = new List<string>();
            s.Failed += f => failed.Add(f);
            s.Start(_state, new Dictionary<string, string> { ["CRASH"] = "1" });
            if (s.Pid is int pid) _pids.Add(pid);
            Thread.Sleep(2500);   // the server is gone by now, but nothing may be raised outside Pump
            Assert.Empty(failed);
            PumpUntil(s, () => failed.Count > 0, "Failed");
            Assert.Contains("3", failed[0]);
        }

        [Fact]
        public void Dispose_IsNotAFailure_AndIsSafeTwice()
        {
            var (s, _) = StartReady();
            var failed = new List<string>();
            s.Failed += f => failed.Add(f);
            s.Dispose();
            for (int i = 0; i < 20; i++) { s.Pump(); Thread.Sleep(25); }
            Assert.Empty(failed);
            s.Dispose();
            Assert.Null(s.Pid);
            new SoloServer(_solo).Dispose();   // never started
        }
    }
}
