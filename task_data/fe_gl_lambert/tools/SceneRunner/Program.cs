using System;
using System.Collections.Generic;
using System.IO;
using System.Numerics;
using Raylib_cs;
using System.Linq;
using System.Text.Json;
using Fastengine;

// Flat quads, each with its own normal, material and lights, drawn with Lambert's shader into an 8-bit target. Saved
// upright to <out>/frame.png; the test probes each quad's centre against three r162's MeshLambertMaterial arithmetic.
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

var shader = Raylib.LoadShaderFromMemory(Lambert.Vertex, Lambert.Fragment);
if (shader.Id == Rlgl.GetShaderIdDefault() || Raylib.GetShaderLocation(shader, "uNormal") < 0)
{
    Console.Error.WriteLine("Lambert's shader did not compile or link (uNormal missing)");
    Raylib.CloseWindow();
    return 2;
}
var frame = Raylib.LoadRenderTexture(Scenes.Columns * Scenes.Cell, Scenes.Rows * Scenes.Cell);
Raylib.BeginTextureMode(frame);
Raylib.ClearBackground(Color.Black);
var index = 0;
foreach (var scene in Scenes.All)
{
    var x = index % Scenes.Columns * Scenes.Cell;
    var y = index / Scenes.Columns * Scenes.Cell;
    Raylib.BeginShaderMode(shader);
    Lambert.Apply(shader, scene.Lights, scene.Material);
    Raylib.SetShaderValue(shader, Raylib.GetShaderLocation(shader, "uNormal"), scene.Normal, ShaderUniformDataType.Vec3);
    Raylib.DrawRectangle(x, y, Scenes.Cell, Scenes.Cell, Color.White);
    Raylib.EndShaderMode();
    index++;
}
Raylib.EndTextureMode();

var img = Raylib.LoadImageFromTexture(frame.Texture);
Raylib.ImageFlipVertical(ref img);
Raylib.ExportImage(img, Path.Combine(outDir, "frame.png"));
Raylib.UnloadImage(img);
File.WriteAllText(Path.Combine(outDir, "scenes.json"), Scenes.Json());
Raylib.UnloadRenderTexture(frame);
Raylib.UnloadShader(shader);
Raylib.CloseWindow();
return 0;

record Scene(string Name, Vector3 Normal, int Material, Light[] Lights);

static class Scenes
{
    public const int Cell = 20, Columns = 8, Rows = 3;
    static readonly Vector3 O = Vector3.Zero;

    static float[] V(Vector3 v) => new[] { v.X, v.Y, v.Z };

    static object Describe(Light l) => l switch
    {
        AmbientLight a => new { kind = "ambient", hex = a.Hex, intensity = a.Intensity },
        HemisphereLight h => new { kind = "hemisphere", hex = h.Hex, ground = h.GroundHex, intensity = h.Intensity },
        DirectionalLight d => (object)new { kind = "directional", hex = d.Hex, intensity = d.Intensity, position = V(d.Position), target = V(d.Target) },
        _ => throw new ArgumentException(l.GetType().Name),
    };

    // The scene list for the test, which computes three's pixel for each quad (cell i at column i % Columns, row i / Columns).
    public static string Json() => JsonSerializer.Serialize(new
    {
        cell = Cell, columns = Columns,
        scenes = All.Select(s => new { name = s.Name, normal = V(s.Normal), material = s.Material, lights = s.Lights.Select(Describe).ToArray() }),
    });

    public static readonly Scene[] All =
    {
        new("ambient_only", Vector3.UnitY, 0xc08040, new Light[] { new AmbientLight(0xffffff, 1.5f) }),
        new("ambient_tinted", Vector3.UnitZ, 0x6699cc, new Light[] { new AmbientLight(0x404060, 2.0f) }),
        new("sun_overhead", Vector3.UnitY, 0x808080, new Light[] { new DirectionalLight(0xffffff, 2.0f, new Vector3(0, 10, 0), O) }),
        new("sun_slanted", Vector3.UnitY, 0x5a8f3c, new Light[] { new DirectionalLight(0xfff4e0, 2.5f, new Vector3(6, 8, 0), O) }),
        new("sun_target_off_origin", Vector3.UnitX, 0x9a7b55, new Light[] { new DirectionalLight(0xffffff, 1.8f, new Vector3(3, 4, 0), new Vector3(-1, 4, 0)) }),
        new("sun_behind_surface", Vector3.UnitY, 0x808080, new Light[] { new AmbientLight(0x202020, 1.0f), new DirectionalLight(0xffffff, 3.0f, new Vector3(0, -5, 2), O) }),
        new("two_suns", Vector3.UnitZ, 0xb0b0b0, new Light[] { new DirectionalLight(0xff8040, 1.2f, new Vector3(0, 0, 5), O), new DirectionalLight(0x4080ff, 1.0f, new Vector3(4, 0, 4), O) }),
        new("hemi_facing_up", Vector3.UnitY, 0xd0c0a0, new Light[] { new HemisphereLight(0x87ceeb, 0x3a2a1a, 1.5f) }),
        new("hemi_facing_down", -Vector3.UnitY, 0xd0c0a0, new Light[] { new HemisphereLight(0x87ceeb, 0x3a2a1a, 1.5f) }),
        new("hemi_sideways", Vector3.UnitX, 0xd0c0a0, new Light[] { new HemisphereLight(0x87ceeb, 0x3a2a1a, 1.5f) }),
        new("hemi_tilted", Vector3.Normalize(new Vector3(1, 1, 0)), 0x70a0d0, new Light[] { new HemisphereLight(0xffffff, 0x000000, 2.0f) }),
        new("hemi_plus_sun", Vector3.Normalize(new Vector3(0, 2, 1)), 0x8c6a4f, new Light[] { new HemisphereLight(0xbfd8ff, 0x52422f, 1.0f), new DirectionalLight(0xffffff, 1.6f, new Vector3(2, 6, 3), O) }),
        new("carrier_deck", Vector3.UnitY, 0x5c6670, new Light[] { new AmbientLight(0x6a7a8a, 0.6f), new HemisphereLight(0x9fc4e8, 0x1e3a50, 0.8f), new DirectionalLight(0xfff1d6, 2.2f, new Vector3(30, 60, 20), O) }),
        new("carrier_hull_side", Vector3.UnitX, 0x5c6670, new Light[] { new AmbientLight(0x6a7a8a, 0.6f), new HemisphereLight(0x9fc4e8, 0x1e3a50, 0.8f), new DirectionalLight(0xfff1d6, 2.2f, new Vector3(30, 60, 20), O) }),
        new("dark_material", Vector3.UnitY, 0x1a1a1a, new Light[] { new AmbientLight(0xffffff, 3.0f) }),
        new("near_black", Vector3.UnitY, 0x202020, new Light[] { new AmbientLight(0x707070, 1.0f) }),
        new("overexposed_clamps", Vector3.UnitY, 0xffe0c0, new Light[] { new DirectionalLight(0xffffff, 8.0f, new Vector3(0, 1, 0), O) }),
        new("dim_red", Vector3.UnitZ, 0xff0000, new Light[] { new AmbientLight(0xffffff, 0.4f) }),
        new("unnormalised_normal", new Vector3(0, 3, 0), 0x808080, new Light[] { new DirectionalLight(0xffffff, 1.5f, new Vector3(0, 2, 2), O) }),
        new("four_suns", Vector3.UnitY, 0xa0a0a0, new Light[] {
            new DirectionalLight(0x400000, 1.0f, new Vector3(1, 2, 0), O), new DirectionalLight(0x004000, 1.0f, new Vector3(-1, 2, 0), O),
            new DirectionalLight(0x000040, 1.0f, new Vector3(0, 2, 1), O), new DirectionalLight(0x404040, 1.0f, new Vector3(0, 2, -1), O) }),
    };
}
