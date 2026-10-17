using System;
using Raylib_cs;

namespace Fastengine
{
    // Offscreen screenshot for scripted runs (-screenshot path): render one frame, save it as PNG, log "[Shot] path".
    public static class Shot
    {
        // Draws the scene (draw gets the target's pixel size), saves it to path as PNG, and returns true.
        public static bool Capture(int width, int height, Action<int, int> draw, string path)
        {
            var target = Raylib.LoadRenderTexture(width, height);
            Raylib.BeginTextureMode(target);
            draw(width, height);
            Raylib.EndTextureMode();
            var image = Raylib.LoadImageFromTexture(target.Texture);
            Raylib.ExportImage(image, path);
            Raylib.UnloadImage(image);
            Raylib.UnloadRenderTexture(target);
            Console.WriteLine($"[Shot] {path}");
            return true;
        }
    }
}
