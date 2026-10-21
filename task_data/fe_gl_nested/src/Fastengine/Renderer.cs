using System;
using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // A cut-down fastengine renderer: flat-coloured or textured meshes, three's onBeforeRender hooks, a camera's
    // projection override, and renderer.setRenderTarget(target) + render() from inside a frame (a mirror's reflection pass).
    public sealed class Renderer : IDisposable
    {
        const string Vertex = @"#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
uniform mat4 mvp;
out vec2 vUv;
void main() { vUv = vertexTexCoord; gl_Position = mvp * vec4(vertexPosition, 1.0); }";

        const string Fragment = @"#version 330
in vec2 vUv;
uniform sampler2D texture0;
uniform vec3 uColor;
uniform int uUseMap;
out vec4 finalColor;
void main() { finalColor = vec4(uUseMap == 1 ? texture(texture0, vUv).rgb : uColor, 1.0); }";

        // The frame's output target: the caller binds it (BeginTextureMode) before rendering the frame into it.
        public RenderTexture2D Target;
        readonly Shader _shader;
        Material _material;

        public Renderer()
        {
            _shader = Raylib.LoadShaderFromMemory(Vertex, Fragment);
            _material = Raylib.LoadMaterialDefault();
            _material.Shader = _shader;
        }

        public void Render(Scene scene, Camera camera)
        {
            RunBeforeRender(scene, camera);
            Rlgl.SetClipPlanes(camera.Near, camera.Far);
            Raylib.BeginMode3D(new Camera3D(camera.Position, camera.Target, camera.Up, camera.Fov, CameraProjection.Perspective));
            foreach (var o in scene.Objects) Draw(o);
            Raylib.EndMode3D();
            Rlgl.EnableDepthMask();
            Rlgl.DisableDepthTest();
            Rlgl.EnableBackfaceCulling();
        }

        void Draw(Obj o)
        {
            Raylib.SetShaderValue(_shader, Raylib.GetShaderLocation(_shader, "uColor"), o.Color, ShaderUniformDataType.Vec3);
            Raylib.SetShaderValue(_shader, Raylib.GetShaderLocation(_shader, "uUseMap"), o.Map.HasValue ? 1 : 0, ShaderUniformDataType.Int);
            unsafe
            {
                _material.Maps[0].Texture = o.Map ?? new Texture2D { Id = Rlgl.GetTextureIdDefault(), Width = 1, Height = 1, Mipmaps = 1, Format = PixelFormat.UncompressedR8G8B8A8 };
            }
            Raylib.DrawMesh(o.Mesh, _material, Matrix4x4.Transpose(o.World));
        }

        void RunBeforeRender(Scene scene, Camera camera)
        {
            var hooks = new List<Obj>();
            foreach (var o in scene.Objects) if (o.OnBeforeRender != null) hooks.Add(o);
            foreach (var o in hooks) o.OnBeforeRender(this, scene, camera);
        }

        // renderer.setRenderTarget(target); renderer.render(scene, camera) from inside a frame (a mirror's pass): the
        // target is cleared to `clear`, and the frame's hooks are not run again.
        public void RenderInto(RenderTexture2D target, Scene scene, Camera camera, Color clear)
        {
            Raylib.BeginTextureMode(target);
            Raylib.ClearBackground(clear);
            Render(scene, camera);
            Raylib.EndTextureMode();
        }

        public void Dispose() => Raylib.UnloadShader(_shader);
    }
}
