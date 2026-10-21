using System;
using System.IO;
using System.Numerics;
using Raylib_cs;
using Fastengine;

// Three scenes, each one Instancing.Build mesh drawn with one Raylib.DrawMesh through a shader made of
// ShaderPort.WrapVertex(Instancing.Attributes(...)) from shaders/*: "palette" (12 quads, two per-instance attributes),
// "cells" (20,000 2x2 px quads, more vertices than raylib's 16-bit indices reach) and "rain" (CarrierDominion's real
// rain shader, verbatim, with its 11,000 seeded drops). Saved upright to <out>/<scene>.png; tests/test_instanced.py checks
// the first two analytically and compares "rain" with tests/fixtures/rain.png (fastengine's own instancing).
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");
var report = new System.Text.StringBuilder();

// three's PlaneGeometry(1, 1): XY, centred, uv 0..1.
float[] planePositions = { -0.5f, 0.5f, 0, 0.5f, 0.5f, 0, -0.5f, -0.5f, 0, 0.5f, -0.5f, 0 };
float[] planeUvs = { 0, 1, 1, 1, 0, 0, 1, 0 };
int[] planeIndices = { 0, 2, 1, 2, 3, 1 };

Shader Load(string name, string uniform)
{
    var vs = ShaderPort.WrapVertex(Instancing.Attributes(File.ReadAllText(Path.Combine("shaders", name + ".vert"))));
    var fs = ShaderPort.WrapFragment(File.ReadAllText(Path.Combine("shaders", name + ".frag")));
    var s = Raylib.LoadShaderFromMemory(vs, fs);
    var ok = s.Id != Rlgl.GetShaderIdDefault() && Raylib.GetShaderLocation(s, uniform) >= 0;
    report.AppendLine($"{name} {(ok ? "compiled" : "failed")}");
    return s;
}

void Save(RenderTexture2D rt, string name)
{
    var img = Raylib.LoadImageFromTexture(rt.Texture);
    Raylib.ImageFlipVertical(ref img);
    Raylib.ExportImage(img, Path.Combine(outDir, name + ".png"));
    Raylib.UnloadImage(img);
}

void Draw2D(string name, string uniform, Mesh mesh, int w, int h)
{
    var shader = Load(name, uniform);
    var material = Raylib.LoadMaterialDefault();
    material.Shader = shader;
    var rt = Raylib.LoadRenderTexture(w, h);
    Raylib.BeginTextureMode(rt);
    Raylib.ClearBackground(Color.Black);
    Rlgl.DisableBackfaceCulling();
    Raylib.DrawMesh(mesh, material, Matrix4x4.Identity);
    Rlgl.EnableBackfaceCulling();
    Raylib.EndTextureMode();
    Save(rt, name);
    Raylib.UnloadRenderTexture(rt);
    Raylib.UnloadShader(shader);
    Raylib.UnloadMesh(mesh);
}

// palette: 4 x 3 quads, 12 px wide, centred at (20 + 40 i, 20 + 40 j) in a y-down 160x120 frame.
{
    var colors = new float[12 * 3];
    var offsets = new float[12 * 2];
    for (var k = 0; k < 12; k++)
    {
        colors[k * 3] = (k % 4 + 1) / 5f;
        colors[k * 3 + 1] = (k / 4 + 1) / 4f;
        colors[k * 3 + 2] = (k * 7 % 12) / 11f;
        offsets[k * 2] = 20 + 40 * (k % 4);
        offsets[k * 2 + 1] = 20 + 40 * (k / 4);
    }
    var mesh = Instancing.Build(planePositions, planeUvs, planeIndices, 12,
        new InstanceAttribute("aColor", 3, colors), new InstanceAttribute("aOffset", 2, offsets));
    Draw2D("palette", "matProjection", mesh, 160, 120);
}

// cells: a 2x2 px quad per cell of a 200x100 grid in a 400x200 frame, instance k at cell (k % 200, k / 200): 80,000 vertices.
{
    var cells = new float[20000 * 2];
    for (var k = 0; k < 20000; k++) { cells[k * 2] = k % 200; cells[k * 2 + 1] = k / 200; }
    var mesh = Instancing.Build(planePositions, planeUvs, planeIndices, 20000, new InstanceAttribute("aCell", 2, cells));
    Draw2D("cells", "matProjection", mesh, 400, 200);
}

// rain: weatherfx.js's buildRain (PlaneGeometry(1, 1), 11,000 drops seeded by its LCG) and a mid-storm frame.
{
    uint s = 20260829;
    var seeds = new float[11000 * 3];
    for (var i = 0; i < seeds.Length; i++) { s = unchecked(s * 1664525 + 1013904223); seeds[i] = (float)(s / 4294967296.0); }
    var mesh = Instancing.Build(planePositions, planeUvs, planeIndices, 11000, new InstanceAttribute("aSeed", 3, seeds));
    var shader = Load("rain", "uFall");
    void F(string n, float v) => Raylib.SetShaderValue(shader, Raylib.GetShaderLocation(shader, n), v, ShaderUniformDataType.Float);
    void V2(string n, Vector2 v) => Raylib.SetShaderValue(shader, Raylib.GetShaderLocation(shader, n), v, ShaderUniformDataType.Vec2);
    void V3(string n, Vector3 v) => Raylib.SetShaderValue(shader, Raylib.GetShaderLocation(shader, n), v, ShaderUniformDataType.Vec3);
    const float strength = 0.7f;
    F("uTime", 37.25f);
    F("uFall", 30 + strength * 26);
    V2("uWind", new Vector2(MathF.Cos(0.6f), -MathF.Sin(0.6f)));
    F("uSlant", 0.12f + 0.6f * 0.55f);
    V3("uBox", new Vector3(64, 42, 64));
    F("uShare", strength);
    F("uLength", 0.7f + strength * 1.1f);
    V3("uColour", new Vector3(0.58f, 0.67f, 0.78f));
    F("uStrength", 0.20f + strength * 0.40f);
    var material = Raylib.LoadMaterialDefault();
    material.Shader = shader;
    var rt = Raylib.LoadRenderTexture(240, 160);
    var camera = new Camera3D(new Vector3(0, 0, 0), new Vector3(0, -0.15f, -1), Vector3.UnitY, 60, CameraProjection.Perspective);
    Raylib.BeginTextureMode(rt);
    Raylib.ClearBackground(new Color(28, 34, 44, 255));
    Raylib.BeginMode3D(camera);
    Rlgl.DisableBackfaceCulling();
    Rlgl.DisableDepthMask();
    Raylib.BeginBlendMode(BlendMode.Alpha);
    Raylib.DrawMesh(mesh, material, Matrix4x4.Identity);
    Raylib.EndBlendMode();
    Rlgl.EnableDepthMask();
    Rlgl.EnableBackfaceCulling();
    Raylib.EndMode3D();
    Raylib.EndTextureMode();
    Save(rt, "rain");
    Raylib.UnloadRenderTexture(rt);
    Raylib.UnloadShader(shader);
    Raylib.UnloadMesh(mesh);
}

File.WriteAllText(Path.Combine(outDir, "compiled.txt"), report.ToString());
Raylib.CloseWindow();
