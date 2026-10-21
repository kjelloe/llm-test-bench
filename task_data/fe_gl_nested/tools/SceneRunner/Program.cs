using System;
using System.IO;
using System.Numerics;
using Raylib_cs;
using Fastengine;

// Two frames, each rendered into a 240x160 frame target the way fastengine's app loop does it: bind the target, clear,
// draw 2D underneath, renderer.Render(scene, camera), draw 2D on top, unbind. Frame 1's scene holds a mirror whose
// onBeforeRender hook renders a second scene into the mirror's own target (RenderInto) with a hand-set projection; the
// mirror quad then shows that target. Frame 2 renders a plain scene after it. Saved upright to <out>/frame1.png and
// frame2.png, the hook counts to <out>/hooks.txt; tests/test_nested.py compares with tests/fixtures (fastengine's own
// RenderInto).
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

static Matrix4x4 At(float x, float y, float z) => Matrix4x4.CreateTranslation(x, y, z);
// A GL off-centre frustum (glFrustum) in System.Numerics layout, as three's makePerspective builds it.
static Matrix4x4 Frustum(float l, float r, float b, float t, float n, float f) => new(
    2 * n / (r - l), 0, 0, 0,
    0, 2 * n / (t - b), 0, 0,
    (r + l) / (r - l), (t + b) / (t - b), -(f + n) / (f - n), -1,
    0, 0, -2 * f * n / (f - n), 0);

var cube = Raylib.GenMeshCube(1, 1, 1);
var quad = Raylib.GenMeshPlane(1, 1, 1, 1);
var renderer = new Renderer();
var frameTarget = Raylib.LoadRenderTexture(240, 160);
var mirrorTarget = Raylib.LoadRenderTexture(128, 64);
renderer.Target = frameTarget;
int frameHooks = 0, nestedHooks = 0;

// The reflected scene: three cubes in a row and a "water" object whose own hook must not run in a nested pass.
var reflected = new Scene();
reflected.Objects.Add(new Obj { Mesh = cube, World = At(-1.5f, 0, 0), Color = new Vector3(0.9f, 0.2f, 0.2f) });
reflected.Objects.Add(new Obj { Mesh = cube, World = At(0, 0, 0), Color = new Vector3(0.2f, 0.85f, 0.3f) });
reflected.Objects.Add(new Obj { Mesh = cube, World = At(1.5f, 0, 0), Color = new Vector3(0.25f, 0.35f, 0.95f),
    OnBeforeRender = (_, _, _) => nestedHooks++ });
var mirrorCamera = new Camera
{
    Position = new Vector3(0, 0.5f, 5), Target = new Vector3(0, 0, 0), Near = 0.5f, Far = 50,
    // An off-centre frustum for the mirror's 2:1 target: the view shifted left and down, as a Reflector's virtual
    // camera sees it.
    Projection = Frustum(-0.5f, 0.3f, -0.25f, 0.15f, 0.5f, 50),
};

// Frame 1: a crate, a pillar and a mirror (a quad standing up, textured with the mirror's target).
var scene = new Scene();
scene.Objects.Add(new Obj { Mesh = cube, World = At(-1.8f, 0.5f, 0), Color = new Vector3(0.8f, 0.55f, 0.2f) });
scene.Objects.Add(new Obj { Mesh = cube, World = Matrix4x4.CreateScale(0.5f, 2.5f, 0.5f) * At(1.9f, 1.25f, -0.5f), Color = new Vector3(0.6f, 0.6f, 0.65f) });
scene.Objects.Add(new Obj
{
    Mesh = quad, World = Matrix4x4.CreateScale(2.4f, 1, 1.2f) * Matrix4x4.CreateRotationX(MathF.PI / 2) * At(0, 1.1f, -1),
    Map = mirrorTarget.Texture,
    OnBeforeRender = (r, _, _) => { frameHooks++; r.RenderInto(mirrorTarget, reflected, mirrorCamera, new Color(30, 40, 70, 255)); },
});
var camera = new Camera { Position = new Vector3(0, 2.2f, 6), Target = new Vector3(0, 0.8f, 0), Fov = 45 };

Raylib.BeginTextureMode(frameTarget);
Raylib.ClearBackground(new Color(12, 12, 16, 255));
Raylib.DrawRectangle(0, 0, 240, 20, new Color(200, 60, 160, 255));      // 2D underneath: a title bar
renderer.Render(scene, camera);
Raylib.DrawRectangle(8, 128, 64, 24, new Color(240, 220, 40, 255));     // 2D on top: a HUD panel
Raylib.EndTextureMode();
Save(frameTarget, "frame1");

// Frame 2: a plain scene after the mirror frame, with no projection set by hand; its one hook counts as a frame hook.
var plain = new Scene();
plain.Objects.Add(new Obj { Mesh = cube, World = Matrix4x4.CreateScale(1.5f) * At(0.5f, 0.75f, 0), Color = new Vector3(0.3f, 0.7f, 0.9f),
    OnBeforeRender = (_, _, _) => frameHooks++ });
Raylib.BeginTextureMode(frameTarget);
Raylib.ClearBackground(new Color(12, 12, 16, 255));
renderer.Render(plain, new Camera { Position = new Vector3(3, 3, 5), Target = new Vector3(0, 0.5f, 0), Fov = 40 });
Raylib.DrawRectangle(176, 8, 56, 16, new Color(240, 220, 40, 255));
Raylib.EndTextureMode();
Save(frameTarget, "frame2");

File.WriteAllText(Path.Combine(outDir, "hooks.txt"), $"frame {frameHooks}\nnested {nestedHooks}\n");
renderer.Dispose();
Raylib.UnloadRenderTexture(mirrorTarget);
Raylib.UnloadRenderTexture(frameTarget);
Raylib.UnloadMesh(cube);
Raylib.UnloadMesh(quad);
Raylib.CloseWindow();

void Save(RenderTexture2D rt, string name)
{
    var img = Raylib.LoadImageFromTexture(rt.Texture);
    Raylib.ImageFlipVertical(ref img);
    Raylib.ExportImage(img, Path.Combine(outDir, name + ".png"));
    Raylib.UnloadImage(img);
}
