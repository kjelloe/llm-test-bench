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

        public SnapshotInterpolator(int delayMs = 100, int capacity = 32, int maxExtrapolationMs = 100)
        {
            throw new NotImplementedException();
        }

        public int DelayMs { get; }
        public int Capacity { get; }
        public int MaxExtrapolationMs { get; }
        public int Count => throw new NotImplementedException();

        public void Push(Snapshot snapshot, long atMs)
        {
            throw new NotImplementedException();
        }

        public List<RenderEntity> Sample(long nowMs)
        {
            throw new NotImplementedException();
        }
    }
}
