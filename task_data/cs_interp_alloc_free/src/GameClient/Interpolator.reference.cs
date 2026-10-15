using System.Collections.Generic;

namespace GameClient
{
    public struct EntityState
    {
        public int Id;
        public double X, Y;
        public int Kind;

        public EntityState(int id, double x, double y, int kind)
        {
            Id = id; X = x; Y = y; Kind = kind;
        }
    }

    public sealed class Snapshot
    {
        public int Tick;
        public readonly List<EntityState> Players = new List<EntityState>();
        public readonly List<EntityState> Bombs = new List<EntityState>();
    }

    // Port of js/interpolator.mjs that allocates nothing per frame: a fixed ring of (time, snapshot) slots, and a
    // linear scan for the previous position of each entity (a handful of entities, so no lookup table is needed).
    public sealed class Interpolator
    {
        struct Entry
        {
            public double AtMs;
            public Snapshot Snap;
        }

        readonly double _delayMs;
        readonly Entry[] _ring;
        int _start, _count;

        public Interpolator(double delayMs = 100, int capacity = 40)
        {
            _delayMs = delayMs;
            _ring = new Entry[capacity];
        }

        Entry At(int i) => _ring[(_start + i) % _ring.Length];

        public void Push(Snapshot snap, double atMs)
        {
            if (_count > 0 && atMs < At(_count - 1).AtMs) return;
            if (_count == _ring.Length)
            {
                _start = (_start + 1) % _ring.Length;
                _count--;
            }
            _ring[(_start + _count) % _ring.Length] = new Entry { AtMs = atMs, Snap = snap };
            _count++;
        }

        public Snapshot Latest => _count > 0 ? At(_count - 1).Snap : null;

        public bool Sample(double nowMs, List<EntityState> players, List<EntityState> bombs)
        {
            players.Clear();
            bombs.Clear();
            if (_count == 0) return false;
            var target = nowMs - _delayMs;
            int older = -1, newer = -1;
            for (var i = 0; i < _count; i++)
            {
                if (At(i).AtMs <= target) older = i;
                else { newer = i; break; }
            }
            if (newer < 0) { Copy(At(_count - 1).Snap, players, bombs); return true; }
            if (older < 0) { Copy(At(newer).Snap, players, bombs); return true; }
            var o = At(older);
            var n = At(newer);
            var span = n.AtMs - o.AtMs;
            var t = span > 0 ? System.Math.Min(1, System.Math.Max(0, (target - o.AtMs) / span)) : 1;
            Lerp(o.Snap.Players, n.Snap.Players, t, players);
            Lerp(o.Snap.Bombs, n.Snap.Bombs, t, bombs);
            return true;
        }

        static void Copy(Snapshot s, List<EntityState> players, List<EntityState> bombs)
        {
            for (var i = 0; i < s.Players.Count; i++) players.Add(s.Players[i]);
            for (var i = 0; i < s.Bombs.Count; i++) bombs.Add(s.Bombs[i]);
        }

        static void Lerp(List<EntityState> oldList, List<EntityState> newList, double t, List<EntityState> output)
        {
            for (var i = 0; i < newList.Count; i++)
            {
                var e = newList[i];
                var found = -1;
                for (var j = oldList.Count - 1; j >= 0; j--)   // last duplicate wins, as with the JS Map
                    if (oldList[j].Id == e.Id) { found = j; break; }
                if (found < 0) { output.Add(e); continue; }
                var prev = oldList[found];
                output.Add(new EntityState(e.Id, prev.X + (e.X - prev.X) * t, prev.Y + (e.Y - prev.Y) * t, e.Kind));
            }
        }
    }
}
