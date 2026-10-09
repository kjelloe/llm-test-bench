using System;

namespace GameClient
{
    /// <summary>
    /// C# port of boombrawl's shared/movement.mjs (with the constants and helpers it uses from
    /// shared/const.mjs and shared/fixedmath.mjs). The server and client prediction both run this
    /// integrator, so the port must produce exactly the same positions as the JavaScript.
    /// </summary>
    public static class Movement
    {
        public delegate bool Blocked(int cx, int cy);

        public static int WorldToCell(int w)
        {
            throw new NotImplementedException();
        }

        public static (int x, int y) StepEntity(int x, int y, int dirX, int dirY, int speed, Blocked blocked)
        {
            throw new NotImplementedException();
        }
    }
}
