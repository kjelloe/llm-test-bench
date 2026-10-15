using System.Collections.Generic;
using System.Linq;

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

    // One server snapshot, as received. The network layer fills it and hands it to Push; it is not changed after.
    public sealed class Snapshot
    {
        public int Tick;
        public readonly List<EntityState> Players = new List<EntityState>();
        public readonly List<EntityState> Bombs = new List<EntityState>();
    }

    // Port of js/interpolator.mjs (boombrawl's real snapshot interpolator for everyone who is not you).
    // Sample runs every frame from Update(); Push runs when a snapshot arrives (20 Hz).
    public sealed class Interpolator
    {
        sealed class Entry
        {
            public double AtMs;
            public Snapshot Snap;
        }

        readonly double _delayMs;
        readonly int _capacity;
        readonly List<Entry> _buffer = new List<Entry>();

        public Interpolator(double delayMs = 100, int capacity = 40)
        {
            _delayMs = delayMs;
            _capacity = capacity;
        }

        public void Push(Snapshot snap, double atMs)
        {
            if (_buffer.Count > 0 && atMs < _buffer[_buffer.Count - 1].AtMs) return;
            _buffer.Add(new Entry { AtMs = atMs, Snap = snap });
            while (_buffer.Count > _capacity) _buffer.RemoveAt(0);
        }

        public Snapshot Latest => _buffer.Count > 0 ? _buffer[_buffer.Count - 1].Snap : null;

        // Fills players and bombs (cleared first) with the state to draw at nowMs; false if nothing has arrived yet.
        public bool Sample(double nowMs, List<EntityState> players, List<EntityState> bombs)
        {
            players.Clear();
            bombs.Clear();
            if (_buffer.Count == 0) return false;
            var target = nowMs - _delayMs;
            var older = _buffer.Where(e => e.AtMs <= target).LastOrDefault();
            var newer = _buffer.FirstOrDefault(e => e.AtMs > target);
            if (newer == null) { Copy(_buffer.Last().Snap, players, bombs); return true; }
            if (older == null) { Copy(newer.Snap, players, bombs); return true; }
            var span = newer.AtMs - older.AtMs;
            var t = span > 0 ? System.Math.Min(1, System.Math.Max(0, (target - older.AtMs) / span)) : 1;
            players.AddRange(LerpList(older.Snap.Players, newer.Snap.Players, t));
            bombs.AddRange(LerpList(older.Snap.Bombs, newer.Snap.Bombs, t));
            return true;
        }

        static void Copy(Snapshot s, List<EntityState> players, List<EntityState> bombs)
        {
            players.AddRange(s.Players.ToList());
            bombs.AddRange(s.Bombs.ToList());
        }

        static IEnumerable<EntityState> LerpList(List<EntityState> oldList, List<EntityState> newList, double t)
        {
            var oldBy = new Dictionary<int, EntityState>();
            foreach (var e in oldList) oldBy[e.Id] = e;
            return newList.Select(e =>
            {
                if (!oldBy.TryGetValue(e.Id, out var prev)) return e;
                return new EntityState(e.Id, prev.X + (e.X - prev.X) * t, prev.Y + (e.Y - prev.Y) * t, e.Kind);
            }).ToList();
        }
    }
}
