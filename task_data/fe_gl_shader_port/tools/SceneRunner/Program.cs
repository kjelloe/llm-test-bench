using System;
using System.IO;
using System.Numerics;
using Raylib_cs;

// Ports CarrierDominion's real three.js shaders (shaders/*, verbatim) with Fastengine.ShaderPort, records whether each
// pair compiled (raylib falls back to its default shader if not), renders one frame per scene into a 160x90 render
// texture and saves it upright as <out>/<scene>.png. tests/test_port.py compares them with tests/fixtures/.
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

string Read(string f) => File.ReadAllText(Path.Combine("shaders", f));
var report = new System.Text.StringBuilder();

// Compiled = raylib did not fall back to its default shader, and the scene's own uniform exists in the program.
Shader Load(string name, string vert, string frag, string uniform)
{
    var s = Raylib.LoadShaderFromMemory(Fastengine.ShaderPort.Vertex(Read(vert)), Fastengine.ShaderPort.Fragment(Read(frag)));
    var ok = s.Id != Rlgl.GetShaderIdDefault() && Raylib.GetShaderLocation(s, uniform) >= 0;
    report.AppendLine($"{name} {(ok ? "compiled" : "failed")}");
    return s;
}

void Set(Shader s, string name, float v) => Raylib.SetShaderValue(s, Raylib.GetShaderLocation(s, name), v, ShaderUniformDataType.Float);
void Set2(Shader s, string name, Vector2 v) => Raylib.SetShaderValue(s, Raylib.GetShaderLocation(s, name), v, ShaderUniformDataType.Vec2);
void Set3(Shader s, string name, Vector3 v) => Raylib.SetShaderValue(s, Raylib.GetShaderLocation(s, name), v, ShaderUniformDataType.Vec3);

void Save(RenderTexture2D rt, string name)
{
    var img = Raylib.LoadImageFromTexture(rt.Texture);
    Raylib.ImageFlipVertical(ref img);
    Raylib.ExportImage(img, Path.Combine(outDir, name + ".png"));
    Raylib.UnloadImage(img);
}

var camera = new Camera3D(new Vector3(0, 260, -700), new Vector3(0, 0, 400), Vector3.UnitY, 50, CameraProjection.Perspective);
var sea = Raylib.GenMeshPlane(3000, 3000, 96, 96);
var rt = Raylib.LoadRenderTexture(160, 90);

foreach (var (scene, frag, uniform) in new[] { ("ocean", "ocean.frag", "uDeep"), ("ocean-detail", "ocean-detail.frag", "uSunDir") })
{
    var s = Load(scene, "ocean.vert", frag, uniform);
    Set(s, "uTime", 12.5f);
    Set3(s, "uShallow", new Vector3(0.10f, 0.42f, 0.52f));
    Set3(s, "uDeep", new Vector3(0.02f, 0.10f, 0.22f));
    Set3(s, "uSky", new Vector3(0.55f, 0.68f, 0.82f));
    Set3(s, "uSunDir", Vector3.Normalize(new Vector3(0.4f, 0.6f, 0.35f)));
    Set3(s, "cameraPosition", camera.Position);
    var material = Raylib.LoadMaterialDefault();
    material.Shader = s;
    Raylib.BeginTextureMode(rt);
    Raylib.ClearBackground(new Color(10, 20, 40, 255));
    Raylib.BeginMode3D(camera);
    Raylib.DrawMesh(sea, material, Matrix4x4.Identity);
    Raylib.EndMode3D();
    Raylib.EndTextureMode();
    Save(rt, scene);
    Raylib.UnloadShader(s);
}

// The sun-beam pass: three's PlaneGeometry(1, 1) (XY, uv 0..1) as a full-screen pass, additive, no camera.
var quad = new Mesh { VertexCount = 4, TriangleCount = 2 };
unsafe
{
    quad.AllocVertices(); quad.AllocTexCoords(); quad.AllocIndices();
    var p = new[] { -0.5f, -0.5f, 0, 0.5f, -0.5f, 0, -0.5f, 0.5f, 0, 0.5f, 0.5f, 0 };
    var t = new[] { 0f, 0, 1, 0, 0, 1, 1, 1 };
    var ix = new ushort[] { 0, 1, 2, 2, 1, 3 };
    for (var i = 0; i < p.Length; i++) quad.Vertices[i] = p[i];
    for (var i = 0; i < t.Length; i++) quad.TexCoords[i] = t[i];
    for (var i = 0; i < ix.Length; i++) quad.Indices[i] = ix[i];
}
Raylib.UploadMesh(ref quad, false);
{
    var s = Load("beam", "beam.vert", "beam.frag", "uStrength");
    Set2(s, "uSun", new Vector2(0.62f, 0.70f));
    Set(s, "uStrength", 0.8f);
    Set3(s, "uColour", new Vector3(1.0f, 0.94f, 0.85f));
    Set(s, "uAspect", 1.78f);
    Set(s, "uTime", 3.0f);
    var material = Raylib.LoadMaterialDefault();
    material.Shader = s;
    Raylib.BeginTextureMode(rt);
    Raylib.ClearBackground(new Color(30, 40, 60, 255));
    Rlgl.DisableDepthTest();
    Rlgl.DisableBackfaceCulling();
    Raylib.BeginBlendMode(BlendMode.Additive);
    Raylib.DrawMesh(quad, material, Matrix4x4.Identity);
    Raylib.EndBlendMode();
    Rlgl.EnableBackfaceCulling();
    Rlgl.EnableDepthTest();
    Raylib.EndTextureMode();
    Save(rt, "beam");
    Raylib.UnloadShader(s);
}
File.WriteAllText(Path.Combine(outDir, "compiled.txt"), report.ToString());
Raylib.UnloadRenderTexture(rt);
Raylib.UnloadMesh(sea);
Raylib.UnloadMesh(quad);
Raylib.CloseWindow();
