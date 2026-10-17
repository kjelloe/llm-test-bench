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
        const int GlSrcAlpha = 0x0302, GlOneMinusSrcAlpha = 0x0303, GlOne = 1, GlFuncAdd = 0x8006;
        readonly RenderTexture2D _target;

        public HudCanvas(int width, int height)
        {
            _target = Raylib.LoadRenderTexture(width, height);
            Raylib.SetTextureFilter(_target.Texture, TextureFilter.Bilinear);   // scaled like the browser scales a canvas
        }

        public int Width => _target.Texture.Width;
        public int Height => _target.Texture.Height;

        public void Paint(Action draw)
        {
            Raylib.BeginTextureMode(_target);
            Raylib.ClearBackground(Color.Blank);
            // fastengine's Painter.Begin: colour blended as usual (so it ends up premultiplied in a cleared target), alpha
            // accumulated as ONE, ONE_MINUS_SRC_ALPHA (not squared by SRC_ALPHA).
            Rlgl.SetBlendFactorsSeparate(GlSrcAlpha, GlOneMinusSrcAlpha, GlOne, GlOneMinusSrcAlpha, GlFuncAdd, GlFuncAdd);
            Raylib.BeginBlendMode(BlendMode.CustomSeparate);
            draw();
            Raylib.EndBlendMode();
            Raylib.EndTextureMode();
        }

        public void Draw(float x, float y, float w, float h, float alpha = 1)
        {
            var a = (byte)Math.Round(alpha * 255);
            // The target holds premultiplied colour (transparent is black): blend and tint it as such (fastengine's
            // RenderTarget.Draw), else edges darken and a scaled-down line gets a dark halo.
            Raylib.BeginBlendMode(BlendMode.AlphaPremultiply);
            Raylib.DrawTexturePro(_target.Texture, new Rectangle(0, 0, Width, -Height), new Rectangle(x, y, w, h), Vector2.Zero, 0,
                new Color(a, a, a, a));
            Raylib.EndBlendMode();
        }

        public void Dispose() => Raylib.UnloadRenderTexture(_target);
    }
}
