using System;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // A small piece of fastengine's three-style renderer: flat surfaces and a mirror. renderer.toneMapping is ACES
    // Filmic with ToneMappingExposure; the canvas is sRGB. The mirror renders the scene into a render target first
    // (three's Reflector: renderer.setRenderTarget(target); renderer.render(scene, camera)) and then shows that
    // target's texture, times its reflectivity, as its surface.
    public sealed class MirrorRenderer : IDisposable
    {
        public float ToneMappingExposure = 1;
        readonly Shader _shader;

        public MirrorRenderer()
        {
            _shader = Raylib.LoadShaderFromMemory(Shaders.Vertex, Shaders.Fragment);
        }

        int Loc(string name) => Raylib.GetShaderLocation(_shader, name);
        void Set(string name, int v) => Raylib.SetShaderValue(_shader, Loc(name), v, ShaderUniformDataType.Int);
        void Set(string name, float v) => Raylib.SetShaderValue(_shader, Loc(name), v, ShaderUniformDataType.Float);
        void Set(string name, Vector3 v) => Raylib.SetShaderValue(_shader, Loc(name), v, ShaderUniformDataType.Vec3);

        void Output()
        {
            Set("uToneMapping", 1);
            Set("uLinearOutput", 0);
            Set("uExposure", ToneMappingExposure);
        }

        // A flat surface of linear colour `linear` covering `area` of the current target (screen pixels).
        public void DrawSurface(Rectangle area, Vector3 linear)
        {
            Output();
            Set("uUseMap", 0);
            Set("uColor", linear);
            Raylib.BeginShaderMode(_shader);
            Raylib.DrawRectangleRec(area, Color.White);
            Raylib.EndShaderMode();
        }

        // The mirror's pass: draw the reflected scene into the target.
        public void RenderReflection(RenderTexture2D target, Action drawScene)
        {
            Raylib.BeginTextureMode(target);
            Raylib.ClearBackground(Color.Black);
            drawScene();
            Raylib.EndTextureMode();
        }

        // The mirror surface: the reflection target's texture times reflectivity, over `area` of the current target.
        public void DrawMirror(Rectangle area, RenderTexture2D target, float reflectivity)
        {
            Output();
            Set("uUseMap", 1);
            Set("uReflectivity", reflectivity);
            Raylib.BeginShaderMode(_shader);
            Raylib.DrawTexturePro(target.Texture, new Rectangle(0, 0, target.Texture.Width, -target.Texture.Height), area,
                Vector2.Zero, 0, Color.White);
            Raylib.EndShaderMode();
        }

        public void Dispose() => Raylib.UnloadShader(_shader);
    }
}
