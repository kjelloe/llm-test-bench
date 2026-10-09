using System;
using System.Collections.Generic;
using System.Linq;

namespace GameClient
{
    // Smooth motion between views, a Unity-side addition: the browser client
    // draws the newest view as it arrives. Interpolation runs on the server's
    // tick, not on arrival time, because at time compression the server sends
    // its ticks in bursts (x16: sixteen views every 50 ms) and arrival times
    // say nothing about when each tick happened. A playback tick advances at
    // the measured tick rate (ticks per second over the last second of
    // arrivals, so speed changes and pauses follow) and is eased toward
    // DelaySeconds behind the newest view. Positions are lerped, headings
    // turn the short way round, and the newer view decides what exists.
    // No UnityEngine, so Tests~ checks it on captured views.
    public class TickInterpolator
    {
        public const int Capacity = 64;

        public double DelaySeconds = 0.1;

        readonly List<(double at, View view)> _buffer = new List<(double at, View view)>();
        double _rate;
        double? _renderTick;

        public View Latest => _buffer.Count == 0 ? null : _buffer[_buffer.Count - 1].view;
        public double Rate => _rate;
        public double RenderTick => _renderTick ?? 0;

        // The rate to assume before arrivals have measured one: tickHz x speed.
        public void SetNominalRate(double ticksPerSecond)
        {
            if (_rate == 0) _rate = ticksPerSecond;
        }

        public void Push(View view, double arrival)
        {
            if (_buffer.Count > 0 && view.tick <= Latest.tick) return;
            _buffer.Add((arrival, view));
            while (_buffer.Count > Capacity) _buffer.RemoveAt(0);
            MeasureRate();
        }

        void MeasureRate()
        {
            var (latestAt, latest) = _buffer[_buffer.Count - 1];
            foreach (var (at, view) in _buffer)
            {
                if (at < latestAt - 1) continue;
                var span = latestAt - at;
                if (span >= 0.2) _rate = (latest.tick - view.tick) / span;
                return;
            }
        }

        // Once per frame: advance the playback tick and ease it toward its
        // target, never past the newest view or before the oldest.
        public void Advance(double dt)
        {
            if (_buffer.Count == 0) return;
            var target = Latest.tick - _rate * DelaySeconds;
            var render = (_renderTick ?? target) + _rate * dt;
            render += (target - render) * (1 - Math.Exp(-dt * 5));
            _renderTick = Math.Max(_buffer[0].view.tick, Math.Min(Latest.tick, render));
        }

        public Sampled Sample(double renderTick)
        {
            if (_buffer.Count == 0) return null;
            View older = null, newer = null;
            foreach (var (_, view) in _buffer)
            {
                if (view.tick <= renderTick) older = view;
                else
                {
                    newer = view;
                    break;
                }
            }
            if (newer == null) return At(Latest);
            if (older == null) return At(newer);
            var t = (renderTick - older.tick) / (newer.tick - older.tick);
            var sampled = new Sampled { View = newer };
            Lerp(sampled.Carriers, older.carriers, newer.carriers, c => c.id, c => (c.x, c.y, c.z, c.heading), t);
            Lerp(sampled.Units, older.units, newer.units, u => u.id, u => (u.x, u.y, u.z, u.heading), t);
            return sampled;
        }

        static void Lerp<T>(Dictionary<int, Pose> into, List<T> oldList, List<T> newList, Func<T, int> id,
            Func<T, (int x, int y, int z, int heading)> pose, double t)
        {
            var oldBy = new Dictionary<int, T>();
            foreach (var e in oldList) oldBy[id(e)] = e;
            foreach (var e in newList)
            {
                var n = pose(e);
                if (!oldBy.TryGetValue(id(e), out var prev))
                {
                    into[id(e)] = new Pose(n.x, n.y, n.z, n.heading);
                    continue;
                }
                var o = pose(prev);
                into[id(e)] = new Pose(o.x + (n.x - o.x) * t, o.y + (n.y - o.y) * t, o.z + (n.z - o.z) * t,
                    o.heading + ShortTurn(o.heading, n.heading) * t);
            }
        }

        static Sampled At(View view)
        {
            var s = new Sampled { View = view };
            foreach (var c in view.carriers) s.Carriers[c.id] = new Pose(c.x, c.y, c.z, c.heading);
            foreach (var u in view.units) s.Units[u.id] = new Pose(u.x, u.y, u.z, u.heading);
            return s;
        }

        // BAM difference the short way round, in -32768..32767.
        public static int ShortTurn(int from, int to) => ((to - from) % 65536 + 65536 + 32768) % 65536 - 32768;
    }

}
