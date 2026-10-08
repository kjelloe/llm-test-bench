using System;
using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    /// <summary>
    /// Buffers authoritative snapshots (20 Hz) and renders remote entities a fixed
    /// delay behind real time, interpolating between the two snapshots that bracket
    /// the render time.
    /// </summary>
    public sealed class SnapshotInterpolator
    {
        public const int CellUnits = 256;
        public const int TeleportDistanceUnits = 512;

        sealed class Entry
        {
            public long AtMs;
            public Snapshot Snap;
        }

        readonly List<Entry> _buffer = new List<Entry>();

        public SnapshotInterpolator(int delayMs = 100, int capacity = 32, int maxExtrapolationMs = 100)
        {
            if (delayMs < 0) throw new ArgumentOutOfRangeException(nameof(delayMs));
            if (capacity < 2) throw new ArgumentOutOfRangeException(nameof(capacity));
            if (maxExtrapolationMs < 0) throw new ArgumentOutOfRangeException(nameof(maxExtrapolationMs));
            DelayMs = delayMs;
            Capacity = capacity;
            MaxExtrapolationMs = maxExtrapolationMs;
        }

        public int DelayMs { get; }
        public int Capacity { get; }
        public int MaxExtrapolationMs { get; }
        public int Count => _buffer.Count;

        public void Push(Snapshot snapshot, long atMs)
        {
            if (snapshot == null) throw new ArgumentNullException(nameof(snapshot));
            if (_buffer.Count > 0)
            {
                Entry last = _buffer[_buffer.Count - 1];
                if (atMs < last.AtMs || snapshot.Tick <= last.Snap.Tick) return;
            }
            _buffer.Add(new Entry { AtMs = atMs, Snap = snapshot });
            while (_buffer.Count > Capacity) _buffer.RemoveAt(0);
        }

        public List<RenderEntity> Sample(long nowMs)
        {
            if (_buffer.Count == 0) return null;
            long target = nowMs - DelayMs;
            Entry newest = _buffer[_buffer.Count - 1];
            var alive = new HashSet<int>();
            foreach (EntityState e in newest.Snap.Entities) alive.Add(e.Id);

            Entry older = null, newer = null;
            foreach (Entry e in _buffer)
            {
                if (e.AtMs <= target) older = e;
                else { newer = e; break; }
            }

            var result = new List<RenderEntity>();
            if (newer == null)
            {
                Entry prev = _buffer.Count >= 2 ? _buffer[_buffer.Count - 2] : null;
                float ahead = Math.Min(target - newest.AtMs, MaxExtrapolationMs);
                Dictionary<int, EntityState> prevById = prev == null ? null : ById(prev.Snap);
                foreach (EntityState e in newest.Snap.Entities)
                {
                    EntityState p = null;
                    if (prevById != null && prevById.TryGetValue(e.Id, out EntityState found) && !e.Teleported &&
                        !Far(found, e))
                        p = found;
                    if (p == null || ahead <= 0)
                    {
                        result.Add(Render(e.Id, e.X, e.Y, e.Heading, p, e));
                        continue;
                    }
                    float span = newest.AtMs - prev.AtMs;
                    float k = ahead / span;
                    result.Add(Render(e.Id, e.X + (e.X - p.X) * k, e.Y + (e.Y - p.Y) * k, e.Heading, p, e));
                }
                return result;
            }

            if (older == null)
            {
                foreach (EntityState e in newer.Snap.Entities)
                    if (alive.Contains(e.Id)) result.Add(Render(e.Id, e.X, e.Y, e.Heading, null, e));
                return result;
            }

            long spanMs = newer.AtMs - older.AtMs;
            float t = spanMs > 0 ? Mathf.Clamp01((float)(target - older.AtMs) / spanMs) : 1f;
            Dictionary<int, EntityState> olderById = ById(older.Snap);
            foreach (EntityState e in newer.Snap.Entities)
            {
                if (!alive.Contains(e.Id)) continue;
                if (!olderById.TryGetValue(e.Id, out EntityState p) || e.Teleported || Far(p, e))
                {
                    result.Add(Render(e.Id, e.X, e.Y, e.Heading, null, e));
                    continue;
                }
                float heading = p.Heading + ShortestBrads(p.Heading, e.Heading) * t;
                result.Add(Render(e.Id, p.X + (e.X - p.X) * t, p.Y + (e.Y - p.Y) * t, heading, p, e));
            }
            return result;
        }

        static Dictionary<int, EntityState> ById(Snapshot s)
        {
            var d = new Dictionary<int, EntityState>();
            foreach (EntityState e in s.Entities) d[e.Id] = e;
            return d;
        }

        static bool Far(EntityState a, EntityState b)
        {
            long dx = b.X - a.X, dy = b.Y - a.Y;
            return dx * dx + dy * dy > (long)TeleportDistanceUnits * TeleportDistanceUnits;
        }

        static int ShortestBrads(byte from, byte to)
        {
            int d = (to - from) & 0xFF;
            return d > 128 ? d - 256 : d;
        }

        static RenderEntity Render(int id, float x, float y, float headingBrads, EntityState from, EntityState to)
        {
            float? motion = null;
            if (from != null && (to.X != from.X || to.Y != from.Y))
                motion = Mathf.Atan2(to.Y - from.Y, to.X - from.X);
            float wrapped = Mathf.Repeat(headingBrads, 256f);
            return new RenderEntity
            {
                Id = id,
                Position = new Vector3(x / CellUnits, 0f, y / CellUnits),
                Rotation = Quaternion.Euler(0f, wrapped * 360f / 256f, 0f),
                MotionHeading = motion
            };
        }
    }
}
