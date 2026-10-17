using System;
using System.IO;
using Raylib_cs;

// Each scene paints a HudCanvas and composites it over an opaque backdrop in a frame render texture, saved upright as
// <out>/<scene>.png; tests/test_composite.py probes the pixels against what a browser shows.
var outDir = args.Length > 0 ? args[0] : "shots";
Directory.CreateDirectory(outDir);
Raylib.SetTraceLogLevel(TraceLogLevel.Warning);
Raylib.SetConfigFlags(ConfigFlags.HiddenWindow);
Raylib.InitWindow(320, 240, "scenes");
var backdrop = new Color(100, 140, 180, 255);

void Frame(string name, Action body)
{
    var frame = Raylib.LoadRenderTexture(200, 120);
    Raylib.BeginTextureMode(frame);
    Raylib.ClearBackground(backdrop);
    body();
    Raylib.EndTextureMode();
    var img = Raylib.LoadImageFromTexture(frame.Texture);
    Raylib.ImageFlipVertical(ref img);
    Raylib.ExportImage(img, Path.Combine(outDir, name + ".png"));
    Raylib.UnloadImage(img);
    Raylib.UnloadRenderTexture(frame);
}

var panel = new Fastengine.HudCanvas(200, 120);
panel.Paint(() =>
{
    Raylib.DrawRectangle(10, 10, 80, 60, new Color(10, 20, 40, 153));      // rgba(10,20,40,0.6) glass panel
    Raylib.DrawRectangle(30, 30, 20, 10, new Color(255, 255, 255, 255));    // opaque text on it
    Raylib.DrawRectangle(110, 10, 60, 60, new Color(255, 80, 0, 102));      // rgba(255,80,0,0.4)
    Raylib.DrawRectangle(140, 40, 50, 50, new Color(40, 200, 120, 128));    // overlaps the orange one
});
Frame("panel", () => panel.Draw(0, 0, 200, 120));
Frame("faded", () => panel.Draw(0, 0, 200, 120, 0.5f));

var lines = new Fastengine.HudCanvas(200, 120);
lines.Paint(() =>
{
    for (var x = 0; x < 200; x += 2) Raylib.DrawRectangle(x, 0, 1, 120, Color.White);   // 1 px lines, every other column
});
Frame("scaled", () => lines.Draw(0, 0, 100, 60));
panel.Dispose();   // GL objects go before the context does
lines.Dispose();
Raylib.CloseWindow();
