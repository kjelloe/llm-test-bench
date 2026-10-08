using System;
using System.Collections.Generic;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    public class PredictorTests
    {
        const int W = 25, H = 17;

        // Border walls plus a pillar on every even/even cell.
        static bool Blocked(int cx, int cy) =>
            cx <= 0 || cy <= 0 || cx >= W - 1 || cy >= H - 1 || (cx % 2 == 0 && cy % 2 == 0);

        static int Center(int cell) => cell * Movement.Cell + Movement.Half;

        /// <summary>Minimal authoritative server for one player, using the same integrator.</summary>
        sealed class FakeServer
        {
            public int X = Center(1), Y = Center(1);
            public int DirX, DirY, Seq, SpeedLevel, Tick;
            public string Phase = "play";
            public string Status = "alive";

            public void SetInput(InputCommand c)
            {
                Seq = c.Seq;
                int dx = Math.Sign(c.Dx), dy = Math.Sign(c.Dy);
                if (dx != 0) dy = 0;
                DirX = dx;
                DirY = dy;
            }

            public void Step()
            {
                Tick++;
                if (Phase == "play" && Status == "alive")
                    (X, Y) = Movement.Step(X, Y, DirX, DirY, Movement.SpeedForLevel(SpeedLevel), Blocked);
            }

            public AuthoritativeSnapshot Snap() => new AuthoritativeSnapshot
            {
                Tick = Tick,
                Phase = Phase,
                Players = new List<PlayerSnapshot>
                {
                    new PlayerSnapshot { Id = 1, Status = Status, X = X, Y = Y, Seq = Seq, SpeedLevel = SpeedLevel }
                }
            };
        }

        sealed class Link
        {
            public readonly FakeServer Server = new FakeServer();
            public readonly Queue<(int at, InputCommand msg)> ToServer = new Queue<(int, InputCommand)>();
            public readonly Queue<(int at, AuthoritativeSnapshot snap)> ToClient = new Queue<(int, AuthoritativeSnapshot)>();
            public readonly List<InputCommand> Outbox = new List<InputCommand>();
            public readonly Predictor Pred;
            // Position after each input seq: predicted at send time vs. authoritative after applying it.
            public readonly Dictionary<int, (int, int)> PredictedAt = new Dictionary<int, (int, int)>();
            public readonly Dictionary<int, (int, int)> ServerAt = new Dictionary<int, (int, int)>();

            public Link()
            {
                Pred = new Predictor(Blocked, Outbox.Add);
                Pred.SetLocalPlayer(1);
            }

            // One round trip = lag ticks each way; after `ticks` the link drains so both sides settle.
            public void Run(int ticks, int lag, Action<int> drive)
            {
                for (int t = 0; t < ticks + lag + 2; t++)
                {
                    if (t < ticks)
                    {
                        drive(t);
                        Pred.Tick();
                        if (Pred.Active) PredictedAt[Outbox[Outbox.Count - 1].Seq] = (Pred.X, Pred.Y);
                        foreach (InputCommand m in Outbox) ToServer.Enqueue((t + lag, m));
                        Outbox.Clear();
                    }
                    while (ToServer.Count > 0 && ToServer.Peek().at <= t) Server.SetInput(ToServer.Dequeue().msg);
                    Server.Step();
                    if (!ServerAt.ContainsKey(Server.Seq)) ServerAt[Server.Seq] = (Server.X, Server.Y);
                    ToClient.Enqueue((t + lag, Server.Snap()));
                    while (ToClient.Count > 0 && ToClient.Peek().at <= t) Pred.OnSnapshot(ToClient.Dequeue().snap);
                }
            }
        }

        static AuthoritativeSnapshot Snap(int tick, string phase, string status, int x, int y, int seq, int speedLevel = 0) =>
            new AuthoritativeSnapshot
            {
                Tick = tick,
                Phase = phase,
                Players = new List<PlayerSnapshot>
                {
                    new PlayerSnapshot { Id = 1, Status = status, X = x, Y = y, Seq = seq, SpeedLevel = speedLevel }
                }
            };

        [Fact]
        public void Constructor_RejectsNulls()
        {
            Assert.Throws<ArgumentNullException>(() => new Predictor(null, _ => { }));
            Assert.Throws<ArgumentNullException>(() => new Predictor(Blocked, null));
            Assert.Throws<ArgumentNullException>(() => new Predictor(Blocked, _ => { }).OnSnapshot(null));
        }

        [Fact]
        public void ConvergesExactlyWithServer_OverLaggyLink()
        {
            var link = new Link();
            link.Run(120, 3, t =>
            {
                if (t == 5) link.Pred.SetDirection(1, 0);
                if (t == 40) link.Pred.SetDirection(0, 1);
                if (t == 80) link.Pred.SetDirection(0, 0);
            });
            Assert.Equal(link.Server.X, link.Pred.X);
            Assert.Equal(link.Server.Y, link.Pred.Y);
            Assert.NotEqual(Center(1), link.Server.X);
            Assert.NotEqual(Center(1), link.Server.Y);
        }

        [Fact]
        public void PredictionMatchesServerEveryTickWhileMoving()
        {
            // Not only after settling: the position predicted when input N is sent must equal the
            // server's position after it applies input N, for every input while moving.
            var link = new Link();
            link.Run(60, 4, t =>
            {
                if (t == 8) link.Pred.SetDirection(1, 0);
                if (t == 30) link.Pred.SetDirection(0, 1);
                if (t == 50) link.Pred.SetDirection(0, 0);
            });
            int compared = 0;
            foreach (KeyValuePair<int, (int, int)> kv in link.PredictedAt)
            {
                if (kv.Key < 8 || !link.ServerAt.ContainsKey(kv.Key)) continue;
                Assert.True(link.ServerAt[kv.Key] == kv.Value,
                    $"seq {kv.Key}: predicted {kv.Value}, server {link.ServerAt[kv.Key]}");
                compared++;
            }
            Assert.True(compared >= 45, $"only {compared} inputs compared");
        }

        [Fact]
        public void WallCollision_AgreesWithServer()
        {
            var link = new Link();
            link.Run(80, 4, t =>
            {
                if (t == 2) link.Pred.SetDirection(-1, 0);
            });
            Assert.Equal(link.Server.X, link.Pred.X);
            Assert.Equal(Movement.Cell + Movement.Body, link.Server.X);
        }

        [Fact]
        public void RapidDirectionChanges_ReplayPendingInputs()
        {
            var link = new Link();
            var dirs = new[] { (1, 0), (0, 1), (-1, 0), (0, -1) };
            link.Run(150, 5, t =>
            {
                if (t % 3 == 0 && t < 140) link.Pred.SetDirection(dirs[(t / 3) % 4].Item1, dirs[(t / 3) % 4].Item2);
                if (t == 140) link.Pred.SetDirection(0, 0);
            });
            Assert.Equal(link.Server.X, link.Pred.X);
            Assert.Equal(link.Server.Y, link.Pred.Y);
        }

        [Fact]
        public void SpeedPowerUpMidFlight_StillConverges()
        {
            var link = new Link();
            link.Run(100, 4, t =>
            {
                if (t == 3) link.Pred.SetDirection(1, 0);
                if (t == 20) link.Server.SpeedLevel = 3;
                if (t == 60) link.Pred.SetDirection(0, 0);
            });
            Assert.Equal(link.Server.X, link.Pred.X);
            Assert.Equal(link.Server.Y, link.Pred.Y);
        }

        [Fact]
        public void Reconcile_DropsExactlyTheAcknowledgedInputs_AndReplaysTheRest()
        {
            var sent = new List<InputCommand>();
            var pred = new Predictor(Blocked, sent.Add);
            pred.SetLocalPlayer(1);
            int x0 = Center(1), y0 = Center(1);
            pred.OnSnapshot(Snap(1, "play", "alive", x0, y0, 0));
            pred.SetDirection(1, 0);
            pred.Tick();
            pred.Tick();
            pred.Tick();
            Assert.Equal(3, pred.PendingCount);
            Assert.Equal(new[] { 1, 2, 3 }, sent.ConvertAll(s => s.Seq));

            // Server applied seq 1 and 2 (two steps right); seq 3 is still in flight.
            int serverX = x0 + 2 * Movement.SpeedBase;
            pred.OnSnapshot(Snap(2, "play", "alive", serverX, y0, 2));
            Assert.Equal(1, pred.PendingCount);
            (int ex, int ey) = Movement.Step(serverX, y0, 1, 0, Movement.SpeedBase, Blocked);
            Assert.Equal(ex, pred.X);
            Assert.Equal(ey, pred.Y);
        }

        [Fact]
        public void Reconcile_ReplaysWithTheSpeedFromTheSnapshot()
        {
            var pred = new Predictor(Blocked, _ => { });
            pred.SetLocalPlayer(1);
            int x0 = Center(1), y0 = Center(1);
            pred.OnSnapshot(Snap(1, "play", "alive", x0, y0, 0));
            pred.SetDirection(1, 0);
            pred.Tick();
            pred.OnSnapshot(Snap(2, "play", "alive", x0, y0, 0, speedLevel: 2));
            (int ex, _) = Movement.Step(x0, y0, 1, 0, Movement.SpeedForLevel(2), Blocked);
            Assert.Equal(ex, pred.X);
        }

        [Fact]
        public void BeforeFirstSnapshot_InputsAreSentButNotPredicted()
        {
            var sent = new List<InputCommand>();
            var pred = new Predictor(Blocked, sent.Add);
            pred.SetLocalPlayer(1);
            pred.SetDirection(1, 0);
            pred.Tick();
            pred.Tick();
            Assert.Equal(2, sent.Count);
            Assert.False(pred.Active);
            Assert.Equal(0, pred.PendingCount);
            Assert.Equal(0, pred.X);
        }

        [Fact]
        public void DeadOrNotPlaying_StopsPredictingAndFollowsServer()
        {
            var pred = new Predictor(Blocked, _ => { });
            pred.SetLocalPlayer(1);
            pred.OnSnapshot(Snap(1, "play", "alive", Center(1), Center(1), 0));
            pred.SetDirection(1, 0);
            pred.Tick();
            pred.Tick();
            pred.OnSnapshot(Snap(2, "play", "dead", Center(3), Center(1), 0));
            Assert.False(pred.Active);
            Assert.Equal(0, pred.PendingCount);
            Assert.Equal(Center(3), pred.X);
            pred.Tick();
            Assert.Equal(Center(3), pred.X);

            pred.OnSnapshot(Snap(3, "over", "alive", Center(5), Center(1), 3));
            Assert.False(pred.Active);
            Assert.Equal(Center(5), pred.X);
        }

        [Fact]
        public void LocalPlayerMissingFromSnapshot_Deactivates()
        {
            var pred = new Predictor(Blocked, _ => { });
            pred.SetLocalPlayer(1);
            pred.OnSnapshot(Snap(1, "play", "alive", Center(1), Center(1), 0));
            pred.SetDirection(1, 0);
            pred.Tick();
            pred.OnSnapshot(new AuthoritativeSnapshot { Tick = 2, Phase = "play" });
            Assert.False(pred.Active);
            Assert.Equal(0, pred.PendingCount);
        }

        [Fact]
        public void StaleOrDuplicateSnapshot_IsIgnored()
        {
            var pred = new Predictor(Blocked, _ => { });
            pred.SetLocalPlayer(1);
            pred.OnSnapshot(Snap(10, "play", "alive", Center(3), Center(1), 0));
            pred.OnSnapshot(Snap(9, "play", "alive", Center(7), Center(1), 0));
            Assert.Equal(Center(3), pred.X);
            pred.OnSnapshot(Snap(10, "play", "alive", Center(9), Center(1), 0));
            Assert.Equal(Center(3), pred.X);
        }

        [Fact]
        public void SetDirection_IsSingleAxisAndValidated()
        {
            var sent = new List<InputCommand>();
            var pred = new Predictor(Blocked, sent.Add);
            pred.SetDirection(1, 1);
            pred.Tick();
            Assert.Equal(1, sent[0].Dx);
            Assert.Equal(0, sent[0].Dy);
            Assert.Throws<ArgumentOutOfRangeException>(() => pred.SetDirection(2, 0));
            Assert.Throws<ArgumentOutOfRangeException>(() => pred.SetDirection(0, -3));
        }

        [Fact]
        public void RenderPosition_IsInMetersWithFractions()
        {
            var pred = new Predictor(Blocked, _ => { });
            pred.SetLocalPlayer(1);
            pred.OnSnapshot(Snap(1, "lobby", "waiting", Center(1), Center(2), 0));
            Vector3 p = pred.RenderPosition;
            Assert.Equal(1.5f, p.x, 4);
            Assert.Equal(0f, p.y, 4);
            Assert.Equal(2.5f, p.z, 4);
        }
    }
}
