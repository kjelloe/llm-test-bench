using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // fixtures.json: a run of consecutive views captured from a real CarrierDominion match
    // (unityworks capture.mjs). The playback-clock tests replay the real problem: at x16 time
    // compression the server sends 16 ticks every 50 ms in one burst.
    public class TickInterpolatorTests
    {
        static readonly List<View> Run = LoadRun();

        static List<View> LoadRun()
        {
            var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures.json")));
            var run = new List<View>();
            foreach (JsonElement v in doc.RootElement.GetProperty("run").EnumerateArray())
            {
                var view = new View { tick = v.GetProperty("tick").GetInt32() };
                foreach (JsonElement c in v.GetProperty("carriers").EnumerateArray()) view.carriers.Add(M(c));
                foreach (JsonElement u in v.GetProperty("units").EnumerateArray()) view.units.Add(M(u));
                run.Add(view);
            }
            return run;
        }

        static Mover M(JsonElement e) => new Mover
        {
            id = e.GetProperty("id").GetInt32(), x = e.GetProperty("x").GetInt32(), y = e.GetProperty("y").GetInt32(),
            z = e.GetProperty("z").GetInt32(), heading = e.GetProperty("heading").GetInt32(),
        };

        static View V(int tick, params Mover[] units) => new View { tick = tick, units = units.ToList() };
        static Mover U(int id, int x, int heading = 0) => new Mover { id = id, x = x, heading = heading };

        [Fact]
        public void ShortTurn_GoesTheShortWayRoundTheBamCircle()
        {
            Assert.Equal(1036, TickInterpolator.ShortTurn(65000, 500));
            Assert.Equal(-1036, TickInterpolator.ShortTurn(500, 65000));
            Assert.Equal(-32768, TickInterpolator.ShortTurn(0, 32768));
            Assert.Equal(0, TickInterpolator.ShortTurn(100, 100));
            Assert.Equal(100, TickInterpolator.ShortTurn(-50, 50));
        }

        [Fact]
        public void CapturedRun_ExactAtTicks_ExactMidpoints_ShortTurnHeadings()
        {
            var interp = new TickInterpolator();
            foreach (View v in Run) interp.Push(v, 0);
            int moving = 0;
            for (int i = 0; i + 1 < Run.Count; i++)
            {
                View a = Run[i], b = Run[i + 1];
                Sampled atTick = interp.Sample(a.tick), mid = interp.Sample(a.tick + 0.5);
                Assert.Equal(b.units.Select(u => u.id).OrderBy(k => k), mid.Units.Keys.OrderBy(k => k));
                foreach (Mover u in b.units)
                {
                    Mover old = a.units.Find(o => o.id == u.id);
                    if (old == null) continue;
                    Pose p = atTick.Units[u.id];
                    Assert.True(p.X == old.x && p.Y == old.y && p.Z == old.z && p.Heading == old.heading, $"unit {u.id} at tick {a.tick}");
                    Pose m = mid.Units[u.id];
                    Assert.True(m.X == (old.x + u.x) / 2.0 && m.Y == (old.y + u.y) / 2.0 && m.Z == (old.z + u.z) / 2.0, $"unit {u.id} midpoint after {a.tick}");
                    Assert.True(Math.Abs(m.Heading - (old.heading + TickInterpolator.ShortTurn(old.heading, u.heading) / 2.0)) < 1e-9, $"unit {u.id} heading");
                    if (old.x != u.x || old.y != u.y) moving++;
                }
                foreach (Mover c in b.carriers)
                {
                    Mover old = a.carriers.Find(o => o.id == c.id);
                    if (old != null) Assert.Equal((old.x + c.x) / 2.0, mid.Carriers[c.id].X);
                }
            }
            Assert.True(moving > 0);
        }

        [Fact]
        public void NewerViewDecidesWhatExists_NewMoversAppearUnlerped()
        {
            var interp = new TickInterpolator();
            interp.Push(V(10, U(1, 0), U(2, 100)), 0);
            interp.Push(V(11, U(1, 256), U(3, 999)), 0.05);
            Sampled s = interp.Sample(10.25);
            Assert.Equal(new[] { 1, 3 }, s.Units.Keys.OrderBy(k => k).ToArray());
            Assert.Equal(64, s.Units[1].X);
            Assert.Equal(999, s.Units[3].X);
            Assert.Same(interp.Latest, s.View);
        }

        [Fact]
        public void OutsideTheBuffer_SamplesAnEndView()
        {
            var interp = new TickInterpolator();
            Assert.Null(interp.Sample(5));
            interp.Push(V(10, U(1, 0)), 0);
            interp.Push(V(12, U(1, 512)), 0.1);
            Assert.Equal(0, interp.Sample(3).Units[1].X);
            Assert.Equal(512, interp.Sample(99).Units[1].X);
        }

        [Fact]
        public void Push_IgnoresStaleAndDuplicateTicks_AndKeepsCapacity()
        {
            var interp = new TickInterpolator();
            interp.Push(V(10, U(1, 0)), 0);
            interp.Push(V(9, U(1, 777)), 0.01);
            interp.Push(V(10, U(1, 888)), 0.02);
            Assert.Equal(10, interp.Latest.tick);
            Assert.Equal(0, interp.Latest.units[0].x);
            for (int t = 11; t < 11 + 2 * TickInterpolator.Capacity; t++) interp.Push(V(t, U(1, t)), t * 0.05);
            Assert.Equal(11 + 2 * TickInterpolator.Capacity - 1 - TickInterpolator.Capacity + 1, (int)interp.Sample(0).View.tick);
        }

        [Fact]
        public void NominalRate_IsUsedOnlyUntilArrivalsMeasureOne()
        {
            var interp = new TickInterpolator();
            interp.SetNominalRate(320);
            Assert.Equal(320, interp.Rate);
            interp.SetNominalRate(20);
            Assert.Equal(320, interp.Rate);
        }

        [Fact]
        public void BurstyServer_RenderTickMovesForward_LagsAboutTheDelay_MeasuresTheRate()
        {
            var clock = new TickInterpolator();
            clock.SetNominalRate(320);
            double last = -1;
            for (int frame = 0; frame < 180; frame++)
            {
                double now = frame / 60.0;
                int burst = (int)Math.Floor(now / 0.05);
                int newest = burst * 16 + 15;
                clock.Push(V(newest, U(1, newest)), burst * 0.05);
                clock.Advance(1 / 60.0);
                if (frame < 60) { last = clock.RenderTick; continue; }
                Assert.True(clock.RenderTick >= last, $"render tick went backwards at frame {frame}");
                double lag = newest - clock.RenderTick;
                Assert.True(lag > 8 && lag < 64, $"frame {frame}: render tick {clock.RenderTick:F1} lags newest {newest} by {lag:F1}");
                last = clock.RenderTick;
            }
            Assert.True(Math.Abs(clock.Rate - 320) < 40, $"measured rate {clock.Rate:F0}, expected about 320");
        }

        [Fact]
        public void Rate_IsMeasuredFromArrivals_AndFollowsASpeedChange()
        {
            // Nominal says real time (20 ticks/s), but the server runs x16 (320/s) in 50 ms bursts,
            // then drops back to x1. The measured rate must follow the arrivals both times.
            var clock = new TickInterpolator();
            clock.SetNominalRate(20);
            int tick = 0;
            double t = 0;
            for (int burst = 0; burst < 40; burst++, t += 0.05) { tick += 16; clock.Push(V(tick, U(1, tick)), t); clock.Advance(0.05); }
            Assert.True(Math.Abs(clock.Rate - 320) < 40, $"x16 rate measured as {clock.Rate:F0}");
            for (int step = 0; step < 60; step++, t += 0.05) { tick += 1; clock.Push(V(tick, U(1, tick)), t); clock.Advance(0.05); }
            Assert.True(Math.Abs(clock.Rate - 20) < 5, $"x1 rate measured as {clock.Rate:F0}");
        }

        [Fact]
        public void RenderTick_IsClampedToTheBuffer()
        {
            var clock = new TickInterpolator();
            clock.SetNominalRate(20);
            clock.Push(V(100, U(1, 0)), 0);
            for (int i = 0; i < 300; i++) clock.Advance(1 / 60.0);
            Assert.Equal(100, clock.RenderTick);
        }
    }
}
