namespace GameClient
{
    // Verbatim port of boombrawl/shared/movement.mjs and the constants it uses
    // (shared/const.mjs, fixedmath.mjs). The server runs the same integrator,
    // so prediction only matches it if every step, clamp and floor division
    // is identical; Tests~ compares this against the JS on captured arenas.
    public static class Movement
    {
        public const int Cell = 256, Half = 128, Body = 108, AssistMin = 64;
        public const int SpeedBase = 56, SpeedStep = 10, SpeedMax = 96;

        public delegate bool Blocked(int cx, int cy);

        public static int WorldToCell(int w) => FloorDiv(w, Cell);

        // One tick. dirX/dirY in {-1, 0, 1}, single axis; x wins if both are set.
        public static (int x, int y) StepEntity(int x, int y, int dirX, int dirY, int speed, Blocked blocked)
        {
            if (dirX != 0) return StepAxis(x, y, dirX, speed, blocked, true);
            if (dirY != 0) return StepAxis(x, y, dirY, speed, blocked, false);
            return (x, y);
        }

        // u runs along the movement axis, v across it (the lane).
        static (int x, int y) StepAxis(int x, int y, int sign, int speed, Blocked blocked, bool horizontal)
        {
            var u = horizontal ? x : y;
            var v = horizontal ? y : x;
            var cv = WorldToCell(v);
            bool IsBlocked(int au, int av) => horizontal ? blocked(au, av) : blocked(av, au);

            var lead = u + sign * (speed + Body);
            var target = WorldToCell(lead);
            if (target == WorldToCell(u) || !IsBlocked(target, cv))
            {
                u += sign * speed;
                v += Clamp(cv * Cell + Half - v, -speed, speed);
            }
            else
            {
                u = sign > 0 ? target * Cell - Body - 1 : (target + 1) * Cell + Body;
                var offset = v - (cv * Cell + Half);
                if (offset >= AssistMin && !IsBlocked(target, cv + 1))
                    v += System.Math.Min(speed, (cv + 1) * Cell + Half - v);
                else if (offset <= -AssistMin && !IsBlocked(target, cv - 1))
                    v -= System.Math.Min(speed, v - ((cv - 1) * Cell + Half));
            }
            return horizontal ? (u, v) : (v, u);
        }

        static int Clamp(int v, int lo, int hi) => v < lo ? lo : v > hi ? hi : v;

        static int FloorDiv(int a, int b)
        {
            var q = a / b;
            return a % b != 0 && (a < 0) != (b < 0) ? q - 1 : q;
        }
    }
}
