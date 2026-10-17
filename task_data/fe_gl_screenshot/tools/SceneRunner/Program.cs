using System;
using System.IO;
using Raylib_cs;

// For each scene: Fastengine.Shot.Capture writes <out>/<scene>.png and its log; then the same scene is drawn into a
// 2x render texture here and read back as is (bottom-up, as GL stores it) to <out>/<scene>-raw2x.png, which the test
// turns into the expected image. Scenes draw in the pixel size they are given (the 2x target).
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");

void Corners(int w, int h)
{
    Raylib.ClearBackground(new Color(20, 30, 50, 255));
    Raylib.DrawRectangle(0, 0, w / 4, h / 4, new Color(220, 40, 40, 255));            // top left
    Raylib.DrawRectangle(w - w / 3, h - h / 5, w / 3, h / 5, new Color(40, 200, 90, 255)); // bottom right
}

void Stripes(int w, int h)
{
    Raylib.ClearBackground(Color.Black);
    for (var x = 0; x < w; x += 2) Raylib.DrawRectangle(x, 0, 1, h, Color.White);       // 1 px at 2x: gray when reduced
    for (var y = h / 2; y < h; y += 2) Raylib.DrawRectangle(0, y, w / 2, 1, new Color(255, 0, 0, 255));
}

void Diagonal(int w, int h)
{
    Raylib.ClearBackground(new Color(240, 240, 240, 255));
    Raylib.DrawTriangle(new System.Numerics.Vector2(w * 0.1f, h * 0.9f), new System.Numerics.Vector2(w * 0.9f, h * 0.9f),
        new System.Numerics.Vector2(w * 0.3f, h * 0.1f), new Color(30, 60, 200, 255));
}

void Solid(int w, int h) => Raylib.ClearBackground(new Color(90, 90, 90, 255));

void LowMark(int w, int h)   // uniform except a small mark near the bottom: not a single-colour frame
{
    Raylib.ClearBackground(new Color(90, 90, 90, 255));
    Raylib.DrawRectangle(w / 2, h - h / 6, w / 8, h / 10, new Color(250, 200, 0, 255));
}

var scenes = new (string name, int w, int h, Action<int, int> draw)[]
{
    ("corners", 120, 80, Corners), ("stripes", 64, 48, Stripes), ("diagonal", 101, 77, Diagonal), ("solid", 40, 30, Solid), ("lowmark", 40, 30, LowMark),
};
foreach (var (name, w, h, draw) in scenes)
{
    var path = Path.Combine(outDir, name + ".png");
    var log = new StringWriter();
    var stdout = Console.Out;
    Console.SetOut(log);
    bool ok;
    try { ok = Fastengine.Shot.Capture(w, h, draw, path); }
    finally { Console.SetOut(stdout); }
    File.WriteAllText(Path.Combine(outDir, name + ".log"), log.ToString());
    File.WriteAllText(Path.Combine(outDir, name + ".result"), ok ? "true" : "false");

    var raw = Raylib.LoadRenderTexture(w * 2, h * 2);
    Raylib.BeginTextureMode(raw);
    draw(w * 2, h * 2);
    Raylib.EndTextureMode();
    var img = Raylib.LoadImageFromTexture(raw.Texture);
    Raylib.ExportImage(img, Path.Combine(outDir, name + "-raw2x.png"));
    Raylib.UnloadImage(img);
    Raylib.UnloadRenderTexture(raw);
}
Raylib.CloseWindow();
