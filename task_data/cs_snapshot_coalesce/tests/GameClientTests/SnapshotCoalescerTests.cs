using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class SnapshotCoalescerTests
    {
        static string Snap(int tick, params (string kind, int unit)[] events)
        {
            string ev = string.Join(",", events.Select(e => $"{{\"kind\":\"{e.kind}\",\"unit\":{e.unit}}}"));
            return $"{{\"type\":\"snapshot\",\"tick\":{tick},\"stateHash\":\"9f3a\",\"view\":{{\"tick\":{tick},\"team\":0," +
                   $"\"carriers\":[{{\"id\":1,\"x\":{tick * 256},\"y\":512}}],\"units\":[],\"events\":[{ev}]}}}}";
        }

        sealed class Rig
        {
            public readonly List<string> Log = new List<string>();
            public int Parses;
            public readonly SnapshotCoalescer C;

            public Rig()
            {
                C = new SnapshotCoalescer(Parse, v => Log.Add($"apply {v.Tick}"),
                    v => Log.Add($"events {v.Tick}: " + string.Join(" ", v.Events.Select(e => $"{e.Kind}{e.Unit}"))),
                    t => Log.Add("other " + JsonDocument.Parse(t).RootElement.GetProperty("type").GetString()));
            }

            View Parse(string text)
            {
                Parses++;
                JsonElement view = JsonDocument.Parse(text).RootElement.GetProperty("view");
                return new View
                {
                    Tick = view.GetProperty("tick").GetInt32(),
                    Events = view.GetProperty("events").EnumerateArray()
                        .Select(e => new GameEvent { Kind = e.GetProperty("kind").GetString(), Unit = e.GetProperty("unit").GetInt32() }).ToList(),
                };
            }

            public List<string> Events() => Log.Where(l => l.StartsWith("events")).ToList();
            public List<string> Applies() => Log.Where(l => l.StartsWith("apply")).ToList();
        }

        [Fact]
        public void ABurst_IsParsedAndAppliedOnce_TheNewestWins()
        {
            var r = new Rig();
            for (int t = 1; t <= 16; t++) r.C.OnMessage(Snap(t));
            Assert.Equal(0, r.Parses);
            r.C.Flush();
            Assert.Equal(new[] { "apply 16" }, r.Applies());
            Assert.Equal(1, r.Parses);
            r.C.Flush();
            Assert.Single(r.Applies());
        }

        [Fact]
        public void SkippedViews_StillDeliverTheirEvents_OnceAndInTickOrder()
        {
            var r = new Rig();
            r.C.OnMessage(Snap(1, ("boom", 7)));
            r.C.OnMessage(Snap(2));
            r.C.OnMessage(Snap(3, ("launch", 2), ("hit", 9)));
            r.C.OnMessage(Snap(4, ("land", 2)));
            r.C.Flush();
            r.C.OnMessage(Snap(5));
            r.C.OnMessage(Snap(6, ("sunk", 1)));
            r.C.Flush();
            r.C.Flush();
            Assert.Equal(new[] { "events 1: boom7", "events 3: launch2 hit9", "events 4: land2", "events 6: sunk1" }, r.Events());
            Assert.Equal(new[] { "apply 4", "apply 6" }, r.Applies());
        }

        [Fact]
        public void TheAppliedView_IsDrawnBeforeItsEventsAreShown_AndAfterEarlierEvents()
        {
            var r = new Rig();
            r.C.OnMessage(Snap(1, ("boom", 7)));
            r.C.OnMessage(Snap(2, ("hit", 3)));
            r.C.Flush();
            Assert.Equal(new[] { "events 1: boom7", "apply 2", "events 2: hit3" }, r.Log);
        }

        [Fact]
        public void SkippedViewsWithoutEvents_AreNeverParsed()
        {
            var r = new Rig();
            for (int t = 1; t <= 320; t++) r.C.OnMessage(t % 64 == 0 ? Snap(t, ("tick", t)) : Snap(t));
            r.C.Flush();
            Assert.Equal(new[] { "apply 320" }, r.Applies());
            Assert.Equal(4 + 1, r.Parses); // the four skipped views with events (64, 128, 192, 256), plus the applied 320
            Assert.Equal(5, r.Events().Count);
        }

        [Fact]
        public void OtherMessages_PassThroughImmediately()
        {
            var r = new Rig();
            r.C.OnMessage(Snap(1));
            r.C.OnMessage("{\"type\":\"speed\",\"speed\":16}");
            r.C.OnMessage("{\"type\":\"rejected\",\"reason\":\"rate\"}");
            Assert.Equal(new[] { "other speed", "other rejected" }, r.Log);
            r.C.Flush();
            Assert.Equal("apply 1", r.Log.Last());
        }

        [Fact]
        public void Welcome_StartsANewMatch_AndDiscardsThePendingView()
        {
            var r = new Rig();
            r.C.OnMessage(Snap(40, ("boom", 1)));
            r.C.OnMessage("{\"type\":\"welcome\",\"team\":2}");
            r.C.Flush();
            Assert.Equal(new[] { "other welcome" }, r.Log);
            Assert.Equal(0, r.Parses);
            r.C.OnMessage(Snap(1));
            r.C.Flush();
            Assert.Equal(new[] { "other welcome", "apply 1" }, r.Log);
        }

        [Fact]
        public void AMessageThatOnlyContainsASnapshot_IsNotOne()
        {
            var r = new Rig();
            r.C.OnMessage("{\"type\":\"log\",\"entry\":{\"type\":\"snapshot\",\"tick\":3,\"view\":{\"tick\":3,\"events\":[]}}}");
            Assert.Equal(new[] { "other log" }, r.Log);
            r.C.Flush();
            Assert.Equal(0, r.Parses);
        }
    }
}
