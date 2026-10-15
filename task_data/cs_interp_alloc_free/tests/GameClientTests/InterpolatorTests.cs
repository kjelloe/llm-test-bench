using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class InterpolatorTests
    {
        // fixtures.json is written by js/make-fixtures.mjs from the real js/interpolator.mjs.
        static readonly JsonElement Root = JsonDocument.Parse(File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "../../../fixtures.json"))).RootElement;

        static Snapshot ToSnapshot(JsonElement s)
        {
            var snap = new Snapshot();
            foreach (var e in s.GetProperty("players").EnumerateArray()) snap.Players.Add(ToState(e));
            foreach (var e in s.GetProperty("bombs").EnumerateArray()) snap.Bombs.Add(ToState(e));
            return snap;
        }

        static EntityState ToState(JsonElement e) => new EntityState(
            e.GetProperty("id").GetInt32(), e.GetProperty("x").GetDouble(), e.GetProperty("y").GetDouble(), e.GetProperty("kind").GetInt32());

        static Interpolator Replay(Action<double, JsonElement, List<EntityState>, List<EntityState>, bool> check)
        {
            var interp = new Interpolator(Root.GetProperty("delayMs").GetDouble(), Root.GetProperty("capacity").GetInt32());
            var players = new List<EntityState>();
            var bombs = new List<EntityState>();
            foreach (var op in Root.GetProperty("ops").EnumerateArray())
            {
                if (op.GetProperty("op").GetString() == "push")
                    interp.Push(ToSnapshot(op.GetProperty("snap")), op.GetProperty("atMs").GetDouble());
                else
                {
                    var now = op.GetProperty("nowMs").GetDouble();
                    var got = interp.Sample(now, players, bombs);
                    check?.Invoke(now, op.GetProperty("expect"), players, bombs, got);
                }
            }
            return interp;
        }

        static void SameList(JsonElement expect, List<EntityState> actual, string what, double now)
        {
            var i = 0;
            foreach (var e in expect.EnumerateArray())
            {
                Assert.True(i < actual.Count, $"{what} at {now}: missing entity {e.GetProperty("id").GetInt32()}");
                var a = actual[i++];
                var x = ToState(e);
                Assert.True(a.Id == x.Id && a.Kind == x.Kind && Math.Abs(a.X - x.X) < 1e-9 && Math.Abs(a.Y - x.Y) < 1e-9,
                    $"{what} at {now}, #{i}: expected {x.Id} ({x.X}, {x.Y}) kind {x.Kind}, got {a.Id} ({a.X}, {a.Y}) kind {a.Kind}");
            }
            Assert.True(i == actual.Count, $"{what} at {now}: {actual.Count - i} extra entities");
        }

        [Fact]
        public void EverySample_MatchesTheJavaScript()
        {
            var samples = 0;
            Replay((now, expect, players, bombs, got) =>
            {
                samples++;
                if (expect.ValueKind == JsonValueKind.Null)
                {
                    Assert.False(got);
                    Assert.Empty(players);
                    Assert.Empty(bombs);
                    return;
                }
                Assert.True(got, $"Sample({now}) returned false");
                SameList(expect.GetProperty("players"), players, "players", now);
                SameList(expect.GetProperty("bombs"), bombs, "bombs", now);
            });
            Assert.True(samples > 300);
        }

        [Fact]
        public void Sample_AllocatesNothingPerFrame()
        {
            var interp = Replay(null);
            var players = new List<EntityState>(64);
            var bombs = new List<EntityState>(64);
            var latest = Root.GetProperty("ops")[Root.GetProperty("ops").GetArrayLength() - 2].GetProperty("nowMs").GetDouble();
            for (var i = 0; i < 2000; i++) interp.Sample(latest - 600 + (i % 700), players, bombs);   // warm up (JIT tiers)
            var before = GC.GetAllocatedBytesForCurrentThread();
            for (var i = 0; i < 5000; i++) interp.Sample(latest - 600 + (i % 700) + 0.37, players, bombs);
            var allocated = GC.GetAllocatedBytesForCurrentThread() - before;
            Assert.True(allocated == 0, $"Sample allocated {allocated} bytes over 5000 frames");
        }

        [Fact]
        public void Push_AllocatesNothingOnceTheBufferIsFull()
        {
            var interp = new Interpolator(100, 8);
            var snaps = new Snapshot[400];
            for (var i = 0; i < snaps.Length; i++)
            {
                snaps[i] = new Snapshot { Tick = i };
                snaps[i].Players.Add(new EntityState(1, i, i, 0));
            }
            for (var i = 0; i < 200; i++) interp.Push(snaps[i], i * 50.0);
            var before = GC.GetAllocatedBytesForCurrentThread();
            for (var i = 200; i < 400; i++) interp.Push(snaps[i], i * 50.0);
            var allocated = GC.GetAllocatedBytesForCurrentThread() - before;
            Assert.True(allocated == 0, $"Push allocated {allocated} bytes for 200 snapshots");
            Assert.Same(snaps[399], interp.Latest);
        }

        [Fact]
        public void KeepsOnlyCapacitySnapshots()
        {
            var interp = new Interpolator(100, 3);
            for (var i = 0; i < 10; i++)
            {
                var s = new Snapshot { Tick = i };
                s.Players.Add(new EntityState(1, i * 10, 0, 0));
                interp.Push(s, i * 50.0);
            }
            var players = new List<EntityState>();
            var bombs = new List<EntityState>();
            Assert.True(interp.Sample(100 + 100, players, bombs));   // older than the 3 kept: the oldest kept one
            Assert.Equal(70, players[0].X);
            Assert.True(interp.Sample(425 + 100, players, bombs));   // halfway between ticks 8 and 9
            Assert.Equal(85, players[0].X);
        }

        [Fact]
        public void EmptyBuffer_AndLatePackets()
        {
            var interp = new Interpolator();
            var players = new List<EntityState> { new EntityState(9, 1, 1, 0) };
            var bombs = new List<EntityState>();
            Assert.False(interp.Sample(1000, players, bombs));
            Assert.Empty(players);
            Assert.Null(interp.Latest);
            var a = new Snapshot();
            var late = new Snapshot();
            interp.Push(a, 1000);
            interp.Push(late, 950);
            Assert.Same(a, interp.Latest);
        }
    }
}
