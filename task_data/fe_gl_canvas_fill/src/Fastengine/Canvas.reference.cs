using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // The HUD's canvas fill (fastengine core/Fastengine.Core/Canvas2D.cs, reduced to one convex path): triangles through
    // rlgl's batch, in screen pixels with y down, so a path can arrive in either winding.
    public static class Canvas
    {
        // Culling is GL state but the triangles are batched: flush on both sides, or a clockwise path (the common case,
        // y down) is culled when the batch draws (fastengine's fix, OPEN-ITEMS incident A05).
        public static void Fill(IReadOnlyList<Vector2> points, Color color)
        {
            if (points.Count < 3) return;
            Rlgl.DrawRenderBatchActive();
            Rlgl.DisableBackfaceCulling();
            Rlgl.Begin(4); // RL_TRIANGLES
            Rlgl.Color4ub(color.R, color.G, color.B, color.A);
            for (var i = 1; i + 1 < points.Count; i++)
            {
                Rlgl.Vertex2f(points[0].X, points[0].Y);
                Rlgl.Vertex2f(points[i].X, points[i].Y);
                Rlgl.Vertex2f(points[i + 1].X, points[i + 1].Y);
            }
            Rlgl.End();
            Rlgl.DrawRenderBatchActive();   // draw them while culling is still off
            Rlgl.EnableBackfaceCulling();   // the 3D renderer relies on it
        }
    }
}
