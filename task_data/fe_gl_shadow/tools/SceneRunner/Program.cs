using System;
using System.IO;
using System.Numerics;
using Raylib_cs;
using Fastengine;

// Two scenes with one shadow-casting directional light each: a ground plane (receives, does not cast), a crate, a
// floating ball and a pillar standing across the edge of the light's shadow camera (all cast and receive). Each frame is
// saved upright to <out>/<scene>.png; tests/test_shadow.py compares them with tests/fixtures (fastengine's own shadows).
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

var ground = Raylib.GenMeshPlane(40, 40, 8, 8);
var crate = Raylib.GenMeshCube(2, 2, 2);
var ball = Raylib.GenMeshSphere(0.8f, 24, 24);
var pillar = Raylib.GenMeshCube(0.6f, 4, 0.6f);
var rt = Raylib.LoadRenderTexture(240, 160);
var camera = new Camera3D(new Vector3(2, 9, 13), new Vector3(0, 0, -1), Vector3.UnitY, 50, CameraProjection.Perspective);
var ambient = new Vector3(0.25f, 0.28f, 0.33f);
var report = new System.Text.StringBuilder();

var scenes = new (string name, ShadowLight light)[]
{
    ("noon", new ShadowLight { Position = new Vector3(5, 10, 3), Target = Vector3.Zero, Intensity = 2.5f, Color = new Vector3(1.0f, 0.95f, 0.85f),
        Left = -5, Right = 5, Top = 5, Bottom = -5, Near = 1, Far = 14, MapSize = 256, Bias = -0.0005f, Radius = 2 }),
    ("evening", new ShadowLight { Position = new Vector3(-7, 6, -1), Target = new Vector3(1, 0, 0), Intensity = 2.0f, Color = new Vector3(1.0f, 0.75f, 0.55f),
        Left = -3, Right = 6, Top = 4, Bottom = -2, Near = 0.5f, Far = 30, MapSize = 512, Bias = -0.001f, NormalBias = 0.02f, Radius = 1 }),
};

foreach (var (name, light) in scenes)
{
    using var renderer = new ShadowRenderer(light.MapSize);
    report.AppendLine($"{name} {(renderer.Compiled ? "compiled" : "failed")}");
    var objects = new (Mesh mesh, Matrix4x4 transform, Vector3 albedo)[]
    {
        (crate, T(0, 1, 0), new Vector3(0.60f, 0.38f, 0.18f)),
        (ball, T(-2.5f, 2.2f, 1.5f), new Vector3(0.25f, 0.45f, 0.70f)),
        (pillar, T(4.6f, 2, -1.5f), new Vector3(0.55f, 0.55f, 0.50f)),
    };
    renderer.DrawShadowMap(light, Array.ConvertAll(objects, o => (o.mesh, o.transform)));
    Raylib.BeginTextureMode(rt);
    Raylib.ClearBackground(new Color(40, 50, 70, 255));
    Raylib.BeginMode3D(camera);
    renderer.SetLight(light, ambient);
    renderer.DrawMesh(ground, new Vector3(0.45f, 0.50f, 0.35f), Matrix4x4.Identity);
    foreach (var (mesh, transform, albedo) in objects) renderer.DrawMesh(mesh, albedo, transform);
    Raylib.EndMode3D();
    Raylib.EndTextureMode();
    var img = Raylib.LoadImageFromTexture(rt.Texture);
    Raylib.ImageFlipVertical(ref img);
    Raylib.ExportImage(img, Path.Combine(outDir, name + ".png"));
    Raylib.UnloadImage(img);
}
File.WriteAllText(Path.Combine(outDir, "compiled.txt"), report.ToString());
Raylib.UnloadRenderTexture(rt);
Raylib.UnloadMesh(ground);
Raylib.UnloadMesh(crate);
Raylib.UnloadMesh(ball);
Raylib.UnloadMesh(pillar);
Raylib.CloseWindow();

// raylib takes matrices column-major: System.Numerics' translation row must be transposed into its last column.
static Matrix4x4 T(float x, float y, float z) => Matrix4x4.Transpose(Matrix4x4.CreateTranslation(x, y, z));
