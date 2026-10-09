using System;
using System.Collections.Generic;

namespace GameClient
{
    /// <summary>
    /// Smooth motion between server views for the Unity client, interpolating on the server's TICK, not
    /// on arrival time: at time compression the server sends its ticks in bursts (x16: sixteen views every
    /// 50 ms), so arrival times say nothing about when each tick happened.
    /// </summary>
    public class TickInterpolator
    {
        public const int Capacity = 64;
        public double DelaySeconds = 0.1;

        public View Latest => throw new NotImplementedException();
        public double Rate => throw new NotImplementedException();
        public double RenderTick => throw new NotImplementedException();

        public void SetNominalRate(double ticksPerSecond) => throw new NotImplementedException();
        public void Push(View view, double arrivalSeconds) => throw new NotImplementedException();
        public void Advance(double dt) => throw new NotImplementedException();
        public Sampled Sample(double renderTick) => throw new NotImplementedException();
        public static int ShortTurn(int from, int to) => throw new NotImplementedException();
    }
}
