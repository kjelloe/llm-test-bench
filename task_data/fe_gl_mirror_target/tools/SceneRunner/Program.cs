using System;
using System.IO;
using System.Numerics;
using Raylib_cs;

// One frame: a lit wall and a crate drawn straight to the frame, a mirror showing the same two surfaces through its
// reflection target, and the crate drawn again after the mirror's pass. Saved upright to <out>/frame.png; the test
// probes it against three's arithmetic.
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

var renderer = new Fastengine.MirrorRenderer { ToneMappingExposure = 1.2f };
var wall = new Vector3(0.18f, 0.25f, 0.40f);
var crate = new Vector3(0.80f, 0.45f, 0.12f);
var reflection = Raylib.LoadRenderTexture(100, 60);
var frame = Raylib.LoadRenderTexture(240, 120);

Raylib.BeginTextureMode(frame);
Raylib.ClearBackground(Color.Black);
renderer.DrawSurface(new Rectangle(0, 0, 120, 60), wall);
renderer.DrawSurface(new Rectangle(0, 60, 60, 60), crate);
Raylib.EndTextureMode();
renderer.RenderReflection(reflection, () =>
{
    renderer.DrawSurface(new Rectangle(0, 0, 50, 60), wall);
    renderer.DrawSurface(new Rectangle(50, 0, 50, 60), crate);
});
Raylib.BeginTextureMode(frame);   // the frame continues after the mirror's pass
renderer.DrawMirror(new Rectangle(130, 10, 100, 60), reflection, 0.7f);
renderer.DrawSurface(new Rectangle(130, 80, 60, 30), crate);
Raylib.EndTextureMode();

var img = Raylib.LoadImageFromTexture(frame.Texture);
Raylib.ImageFlipVertical(ref img);
Raylib.ExportImage(img, Path.Combine(outDir, "frame.png"));
Raylib.UnloadImage(img);
Raylib.UnloadRenderTexture(reflection);
Raylib.UnloadRenderTexture(frame);
renderer.Dispose();
Raylib.CloseWindow();
