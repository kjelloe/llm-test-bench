using Fastengine.Net;
using Xunit;

namespace FastengineTests
{
    public class SessionTests
    {
        const string Server = "ws://box:8080/play?code=AB12";
        static readonly HashSet<int> Final = new() { 4001, 4003 };

        static (Session s, Dictionary<string, string> settings) New() { var d = new Dictionary<string, string>(); return (new Session(d, Final), d); }

        static string Welcome(string token, bool spectator = false) =>
            $"{{\"type\":\"welcome\",\"team\":{(spectator ? -1 : 1)},\"spectator\":{(spectator ? "true" : "false")},\"token\":\"{token}\"}}";

        static string Query(string url, string name)
        {
            foreach (var p in new Uri(url).Query.TrimStart('?').Split('&'))
                if (p.Split('=')[0] == name) return Uri.UnescapeDataString(p[(name.Length + 1)..]);
            return null;
        }

        [Fact]
        public void Close_RetriesWithBackoff_ResetOnOpen()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0.1);
            double t = 10;
            var delays = new List<double>();
            for (int i = 0; i < 6; i++)
            {
                s.Closed(1006, "gone", t);
                Assert.Equal("reconnecting", s.State);
                Assert.Null(s.Tick(t));
                double at = t;
                while (s.Tick(at) == null) { at = Math.Round(at + 0.001, 3); Assert.True(at < t + 10, "no retry within 10 s"); }
                Assert.Equal("connecting", s.State);
                delays.Add(Math.Round(at - t, 3));
                t = at;
            }
            Assert.Equal(new[] { 1, 1.7, 2.89, 4.913, 5, 5 }, delays);
            s.Opened(t);
            Assert.Equal("open", s.State);
            s.Closed(1006, "gone", 100);
            Assert.Null(s.Tick(100.999));
            Assert.NotNull(s.Tick(101));
        }

        [Fact]
        public void Rejected_BeforeWelcome_Stops_AfterWelcome_DoesNot()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0);
            s.Message("{\"type\":\"rejected\",\"reason\":\"protocol 3 required\"}", 0.1);
            s.Closed(1000, "", 0.2);
            Assert.Equal("stopped", s.State);
            Assert.Equal("refused: protocol 3 required", s.StopReason);
            Assert.Null(s.Tick(60));

            var (t, _) = New();
            t.Connect(Server, false, 0);
            t.Opened(0);
            t.Message(Welcome("abc"), 0.1);
            t.Message("{\"type\":\"rejected\",\"reason\":\"not your carrier\"}", 0.2);
            Assert.Equal("open", t.State);
            t.Closed(1006, "", 1);
            Assert.Equal("reconnecting", t.State);
        }

        [Fact]
        public void Rejected_OnAReconnect_BeforeItsWelcome_Stops()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0);
            s.Message(Welcome("abc"), 0.1);
            s.Closed(1006, "", 1);
            Assert.NotNull(s.Tick(2));
            s.Opened(2.1);
            s.Message("{\"type\":\"rejected\",\"reason\":\"room is gone\"}", 2.2);
            Assert.Equal("stopped", s.State);
            Assert.Equal("refused: room is gone", s.StopReason);
        }

        [Fact]
        public void Kicked_And_FinalCodes_Stop_ForGood()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0);
            s.Message(Welcome("abc"), 0.1);
            s.Message("{\"type\":\"kicked\",\"reason\":\"host removed you\"}", 1);
            s.Closed(1006, "", 1.1);
            Assert.Equal("stopped", s.State);
            Assert.Equal("kicked: host removed you", s.StopReason);
            s.QueueOverflow(2);
            Assert.Equal("stopped", s.State);
            Assert.Null(s.Tick(100));

            var (f, _) = New();
            f.Connect(Server, false, 0);
            f.Opened(0);
            f.Closed(4003, "game over", 5);
            Assert.Equal("stopped", f.State);
            Assert.Equal("close 4003", f.StopReason);
            Assert.Null(f.Tick(60));
            Assert.NotNull(f.Connect(Server, false, 70));
            Assert.Equal("connecting", f.State);
            Assert.Null(f.StopReason);
        }

        [Fact]
        public void Halted_ChangesNothing()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0);
            s.Message(Welcome("abc"), 0.1);
            s.Message("{\"type\":\"halted\",\"reason\":\"paused\"}", 1);
            Assert.Equal("open", s.State);
            Assert.Null(s.StopReason);
        }

        [Fact]
        public void QueueOverflow_ReconnectsAtOnce()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0);
            s.Message(Welcome("abc"), 0.1);
            s.QueueOverflow(3);
            Assert.Equal("reconnecting", s.State);
            var url = s.Tick(3);
            Assert.NotNull(url);
            Assert.Equal("abc", Query(url, "token"));
        }

        [Fact]
        public void Token_IsSavedPerServer_AndSentOnReconnectAndRestart()
        {
            var (s, settings) = New();
            Assert.Null(Query(s.Connect(Server, false, 0), "token"));
            s.Opened(0);
            s.Message(Welcome("seat-1"), 0.1);
            Assert.Equal("seat-1", settings["token:ws://box:8080"]);
            s.Closed(1006, "", 1);
            var again = s.Tick(2);
            Assert.Equal("seat-1", Query(again, "token"));
            Assert.Equal("AB12", Query(again, "code"));

            var other = new Session(settings, Final);
            Assert.Null(Query(other.Connect("wss://elsewhere/play", false, 0), "token"));
            other.Opened(0);
            other.Message(Welcome("seat-9"), 0.1);
            Assert.Equal("seat-9", settings["token:wss://elsewhere"]);
            Assert.Equal("seat-1", settings["token:ws://box:8080"]);

            var restart = new Session(settings, Final);
            Assert.Equal("seat-1", Query(restart.Connect("ws://box:8080/play?token=stale", false, 0), "token"));
        }

        [Fact]
        public void Spectators_NeverSendOrSaveAToken()
        {
            var (s, settings) = New();
            settings["token:ws://box:8080"] = "seat-1";
            var url = s.Connect(Server + "&spectate=1&token=x", true, 0);
            Assert.Null(Query(url, "token"));
            s.Opened(0);
            s.Message(Welcome("watch-7", spectator: true), 0.1);
            Assert.Equal("seat-1", settings["token:ws://box:8080"]);
            s.Closed(1006, "", 1);
            Assert.Null(Query(s.Tick(2), "token"));
        }

        [Fact]
        public void MaxGap_CountsOnlyWithinAConnection()
        {
            var (s, _) = New();
            s.Connect(Server, false, 0);
            s.Opened(0);
            foreach (var t in new[] { 1.0, 1.05, 1.1, 1.4, 1.45 }) s.Message("{\"type\":\"snapshot\"}", t);
            Assert.Equal(0.3, s.MaxGap, 6);
            s.Closed(1006, "drop", 1.5);
            Assert.NotNull(s.Tick(2.5));
            s.Opened(2.6);
            foreach (var t in new[] { 2.7, 2.75, 2.85 }) s.Message("{\"type\":\"snapshot\"}", t);
            Assert.Equal(0.3, s.MaxGap, 6);
            s.QueueOverflow(3);
            Assert.NotNull(s.Tick(3));
            s.Opened(3.5);
            s.Message("{\"type\":\"snapshot\"}", 3.6);
            Assert.Equal(0.3, s.MaxGap, 6);
            s.Message("{\"type\":\"snapshot\"}", 4.2);
            Assert.Equal(0.6, s.MaxGap, 6);
        }
    }
}
