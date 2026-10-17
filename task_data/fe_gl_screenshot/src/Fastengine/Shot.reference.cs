using System;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // fastengine's screenshot path (core/Fastengine.Core/App.cs: the 2x scene target, Blit, SaveShot), as one call.
    public static class Shot
    {
        public static unsafe bool Capture(int width, int height, Action<int, int> draw, string path)
        {
            var scene = Raylib.LoadRenderTexture(width * 2, height * 2);
            var output = Raylib.LoadRenderTexture(width, height);
            Raylib.SetTextureFilter(scene.Texture, TextureFilter.Bilinear);
            try
            {
                Raylib.BeginTextureMode(scene);
                draw(width * 2, height * 2);
                Raylib.EndTextureMode();

                // A render target's texture is stored bottom-up: a negative source height draws it upright. Halving
                // with bilinear filtering samples between four texels, i.e. a 2x2 box filter.
                Raylib.BeginTextureMode(output);
                Raylib.ClearBackground(Color.Black);
                Raylib.DrawTexturePro(scene.Texture, new Rectangle(0, 0, scene.Texture.Width, -scene.Texture.Height),
                    new Rectangle(0, 0, width, height), Vector2.Zero, 0, Color.White);
                Raylib.EndTextureMode();

                var image = Raylib.LoadImageFromTexture(output.Texture);
                Raylib.ImageFlipVertical(ref image);   // GL's origin is bottom-left
                var colors = Raylib.LoadImageColors(image);
                var first = colors[0];
                var single = true;
                for (var i = 1; i < image.Width * image.Height && single; i++)
                    single = colors[i].R == first.R && colors[i].G == first.G && colors[i].B == first.B;
                Raylib.UnloadImageColors(colors);
                Raylib.ExportImage(image, path);
                Raylib.UnloadImage(image);
                if (single)
                {
                    Console.WriteLine("[Shot] image is a single colour");
                    return false;
                }
                Console.WriteLine($"[Shot] {path}");
                return true;
            }
            finally
            {
                Raylib.UnloadRenderTexture(scene);
                Raylib.UnloadRenderTexture(output);
            }
        }
    }
}
