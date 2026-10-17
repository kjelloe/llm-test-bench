using System;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // An offscreen HUD canvas (a CanvasTexture or a RenderTarget drawn into the HUD), like a browser <canvas>: Paint
    // clears it to transparent and runs the draw calls into it; Draw composites it into the current frame at
    // (x, y, w, h) with an extra alpha, as the browser composites a canvas over the page.
    public sealed class HudCanvas : IDisposable
    {
        readonly RenderTexture2D _target;

        public HudCanvas(int width, int height)
        {
            _target = Raylib.LoadRenderTexture(width, height);
        }

        public int Width => _target.Texture.Width;
        public int Height => _target.Texture.Height;

        public void Paint(Action draw)
        {
            Raylib.BeginTextureMode(_target);
            Raylib.ClearBackground(Color.Blank);
            draw();
            Raylib.EndTextureMode();
        }

        public void Draw(float x, float y, float w, float h, float alpha = 1)
        {
            var a = (byte)Math.Round(alpha * 255);
            // Stored bottom-up: a negative source height draws it upright.
            Raylib.DrawTexturePro(_target.Texture, new Rectangle(0, 0, Width, -Height), new Rectangle(x, y, w, h), Vector2.Zero, 0,
                new Color((byte)255, (byte)255, (byte)255, a));
        }

        public void Dispose() => Raylib.UnloadRenderTexture(_target);
    }
}
