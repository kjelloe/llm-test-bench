using System;

namespace GameClient
{
    /// <summary>
    /// The one movement integrator. The Node server runs the identical integer math every
    /// tick; client prediction must run exactly this, or the local player rubber-bands.
    /// Positions are fixed-point: 256 units per grid cell, entities centered at 128.
    /// </summary>
    public static class Movement
    {
        public const int Cell = 256;
        public const int Half = 128;
        public const int Body = 108;       // player half-extent
        public const int AssistMin = 64;   // lane offset before a corner slide kicks in
        public const int SpeedBase = 56;   // units per tick
        public const int SpeedStep = 10;   // per speed power-up level
        public const int SpeedMax = 96;

        public static int SpeedForLevel(int level) => Math.Min(SpeedMax, SpeedBase + level * SpeedStep);

        // Floor division, matching JavaScript's Math.floor(w / 256) for negative values too.
        public static int WorldToCell(int w) => w >= 0 ? w / Cell : -((-w + Cell - 1) / Cell);

        /// <summary>One tick of movement. dirX/dirY in {-1,0,1}; if both are set, X wins.</summary>
        public static (int x, int y) Step(int x, int y, int dirX, int dirY, int speed, Func<int, int, bool> blocked)
        {
            if (dirX != 0) return StepAxis(x, y, dirX, speed, blocked, true);
            if (dirY != 0) return StepAxis(x, y, dirY, speed, blocked, false);
            return (x, y);
        }

        static (int x, int y) StepAxis(int x, int y, int sign, int speed, Func<int, int, bool> blocked, bool horizontal)
        {
            int u = horizontal ? x : y;
            int v = horizontal ? y : x;
            int cv = WorldToCell(v);
            Func<int, int, bool> isBlocked = (au, av) => horizontal ? blocked(au, av) : blocked(av, au);

            int lead = u + sign * (speed + Body);
            int target = WorldToCell(lead);
            if (target == WorldToCell(u) || !isBlocked(target, cv))
            {
                u += sign * speed;
                v += Clamp(cv * Cell + Half - v, -speed, speed);
            }
            else
            {
                u = sign > 0 ? target * Cell - Body - 1 : (target + 1) * Cell + Body;
                int offset = v - (cv * Cell + Half);
                if (offset >= AssistMin && !isBlocked(target, cv + 1))
                    v += Math.Min(speed, (cv + 1) * Cell + Half - v);
                else if (offset <= -AssistMin && !isBlocked(target, cv - 1))
                    v -= Math.Min(speed, v - ((cv - 1) * Cell + Half));
            }
            return horizontal ? (u, v) : (v, u);
        }

        static int Clamp(int v, int lo, int hi) => v < lo ? lo : v > hi ? hi : v;
    }
}
