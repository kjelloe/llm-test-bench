using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // The HUD's canvas fill (fastengine core/Fastengine.Core/Canvas2D.cs, reduced to one convex path): triangles through
    // rlgl's batch, in screen pixels with y down, so a path can arrive in either winding.
    public static class Canvas
    {
        public static void Fill(IReadOnlyList<Vector2> points, Color color)
        {
            if (points.Count < 3) return;
            Rlgl.Begin(4); // RL_TRIANGLES
            Rlgl.Color4ub(color.R, color.G, color.B, color.A);
            for (var i = 1; i + 1 < points.Count; i++)
            {
                Rlgl.Vertex2f(points[0].X, points[0].Y);
                Rlgl.Vertex2f(points[i].X, points[i].Y);
                Rlgl.Vertex2f(points[i + 1].X, points[i + 1].Y);
            }
            Rlgl.End();
        }
    }
}
