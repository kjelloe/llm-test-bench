using System;
using System.Collections.Generic;
using System.IO;
using System.Numerics;
using Raylib_cs;

// Draws each scene into a render texture (rlgl's default state: back-face culling on) and saves it upright as
// <out>/<scene>.png; tests/test_fill.py probes the pixels. Canvas.Fill gets screen pixels, y down.
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

static List<Vector2> P(params float[] xy)
{
    var l = new List<Vector2>();
    for (var i = 0; i < xy.Length; i += 2) l.Add(new Vector2(xy[i], xy[i + 1]));
    return l;
}

// A triangle sent straight to rlgl, outside Canvas.Fill (the 3D renderer's kind of draw, relying on culling).
static void RawTriangle(Vector2 a, Vector2 b, Vector2 c, Color col)
{
    Rlgl.Begin(4);
    Rlgl.Color4ub(col.R, col.G, col.B, col.A);
    Rlgl.Vertex2f(a.X, a.Y); Rlgl.Vertex2f(b.X, b.Y); Rlgl.Vertex2f(c.X, c.Y);
    Rlgl.End();
}

var bg = new Color(16, 16, 16, 255);
var scenes = new (string name, Action draw)[]
{
    ("windings", () =>
    {
        Fastengine.Canvas.Fill(P(10, 10, 70, 10, 70, 70, 10, 70), new Color(220, 40, 40, 255));   // clockwise on screen
        Fastengine.Canvas.Fill(P(90, 10, 90, 70, 150, 40), new Color(40, 80, 220, 255));           // anticlockwise
    }),
    ("polygons", () =>
    {
        var hex = new List<Vector2>();
        for (var i = 0; i < 6; i++) hex.Add(new Vector2(50 + 35 * MathF.Cos(i * MathF.PI / 3), 60 + 35 * MathF.Sin(i * MathF.PI / 3)));
        Fastengine.Canvas.Fill(hex, new Color(40, 200, 90, 255));                                  // clockwise (y down)
        hex.Reverse();
        for (var i = 0; i < hex.Count; i++) hex[i] += new Vector2(90, 0);
        Fastengine.Canvas.Fill(hex, new Color(240, 200, 0, 255));                                  // anticlockwise
    }),
    ("state", () =>
    {
        // Back-facing (clockwise on screen) triangles before and after the fill must stay culled; a front-facing one
        // after it must still draw.
        RawTriangle(new Vector2(10, 10), new Vector2(60, 10), new Vector2(10, 60), Color.White);
        Fastengine.Canvas.Fill(P(80, 10, 140, 10, 140, 70, 80, 70), new Color(220, 40, 40, 255));
        RawTriangle(new Vector2(160, 10), new Vector2(210, 10), new Vector2(160, 60), Color.White);
        RawTriangle(new Vector2(230, 10), new Vector2(230, 60), new Vector2(280, 10), new Color(40, 80, 220, 255));
    }),
};
foreach (var (name, draw) in scenes)
{
    var rt = Raylib.LoadRenderTexture(300, 100);
    Raylib.BeginTextureMode(rt);
    Raylib.ClearBackground(bg);
    draw();
    Raylib.EndTextureMode();
    var img = Raylib.LoadImageFromTexture(rt.Texture);
    Raylib.ImageFlipVertical(ref img);
    Raylib.ExportImage(img, Path.Combine(outDir, name + ".png"));
    Raylib.UnloadImage(img);
    Raylib.UnloadRenderTexture(rt);
}
Raylib.CloseWindow();
