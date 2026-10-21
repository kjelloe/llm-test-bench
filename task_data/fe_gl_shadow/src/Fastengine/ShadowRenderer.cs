using System;
using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // A cut-down fastengine renderer: MeshLambertMaterial-style lighting (ambient + one shadow-casting directional light,
    // albedo / pi, sRGB output), with the light's direct term scaled by Shadows.Glsl's shadowMask. Not editable.
    public sealed class ShadowRenderer : IDisposable
    {
        const string Vertex = @"#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform mat4 uShadowMatrix;
uniform float uShadowNormalBias;
out vec3 vNormal;
out vec4 vShadowCoord;
void main() {
    vec3 world = (matModel * vec4(vertexPosition, 1.0)).xyz;
    vNormal = normalize(mat3(matNormal) * vertexNormal);
    vShadowCoord = uShadowMatrix * vec4(world + vNormal * uShadowNormalBias, 1.0);
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}";

        const string FragmentHead = @"#version 330
in vec3 vNormal;
in vec4 vShadowCoord;
uniform vec3 uAlbedo;
uniform vec3 uAmbient;
uniform vec3 uLightColor;
uniform vec3 uLightDir;
out vec4 finalColor;
";

        const string FragmentMain = @"
vec3 toSRGB(vec3 c) {
    return mix(pow(c, vec3(0.41666)) * 1.055 - vec3(0.055), c * 12.92, vec3(lessThanEqual(c, vec3(0.0031308))));
}
void main() {
    vec3 n = normalize(vNormal);
    float d = max(dot(n, uLightDir), 0.0);
    vec3 irradiance = uAmbient + uLightColor * d * (d > 0.0 ? shadowMask(vShadowCoord) : 1.0);
    finalColor = vec4(toSRGB(clamp(uAlbedo * irradiance * 0.3183098861837907, 0.0, 1.0)), 1.0);
}";

        const string DepthVertex = @"#version 330
in vec3 vertexPosition;
uniform mat4 mvp;
void main() { gl_Position = mvp * vec4(vertexPosition, 1.0); }";

        const string DepthFragment = @"#version 330
out vec4 finalColor;
void main() { finalColor = vec4(1.0); }";

        public readonly Shader Shader, Depth;
        Material _material, _depthMaterial;
        readonly uint _fbo, _depthTexture;
        readonly int _size;

        public ShadowRenderer(int mapSize)
        {
            _size = mapSize;
            Shader = Raylib.LoadShaderFromMemory(Vertex, FragmentHead + Shadows.Glsl + FragmentMain);
            Depth = Raylib.LoadShaderFromMemory(DepthVertex, DepthFragment);
            _material = Raylib.LoadMaterialDefault();
            _material.Shader = Shader;
            _depthMaterial = Raylib.LoadMaterialDefault();
            _depthMaterial.Shader = Depth;
            _fbo = Rlgl.LoadFramebuffer();
            _depthTexture = Rlgl.LoadTextureDepth(mapSize, mapSize, false);
            Rlgl.FramebufferAttach(_fbo, _depthTexture, FramebufferAttachType.Depth, FramebufferAttachTextureType.Texture2D, 0);
            unsafe
            {
                _material.Maps[1].Texture = new Texture2D { Id = _depthTexture, Width = mapSize, Height = mapSize, Mipmaps = 1, Format = PixelFormat.UncompressedR32 };
            }
        }

        // Whether the scene shader compiled with Shadows.Glsl (raylib falls back to its default shader otherwise).
        public bool Compiled => Shader.Id != Rlgl.GetShaderIdDefault() && Raylib.GetShaderLocation(Shader, "uShadowMatrix") >= 0;

        void Set(string name, Vector3 v) => Raylib.SetShaderValue(Shader, Raylib.GetShaderLocation(Shader, name), v, ShaderUniformDataType.Vec3);
        void Set(string name, float v) => Raylib.SetShaderValue(Shader, Raylib.GetShaderLocation(Shader, name), v, ShaderUniformDataType.Float);

        // The depth pass: the casters from the light's camera into the depth texture. Call outside any texture mode.
        public void DrawShadowMap(ShadowLight light, IEnumerable<(Mesh mesh, Matrix4x4 transform)> casters)
        {
            Rlgl.DrawRenderBatchActive();
            Rlgl.EnableFramebuffer(_fbo);
            Rlgl.Viewport(0, 0, _size, _size);
            Rlgl.ClearScreenBuffers();
            Rlgl.SetMatrixProjection(Matrix4x4.Transpose(Shadows.LightMatrix(light)));
            Rlgl.SetMatrixModelView(Matrix4x4.Identity);
            Rlgl.EnableDepthTest();
            Rlgl.EnableDepthMask();
            Shadows.CullForDepthPass();
            foreach (var (mesh, transform) in casters) Raylib.DrawMesh(mesh, _depthMaterial, transform);
            Rlgl.DrawRenderBatchActive();
            Rlgl.SetCullFace(1);
            Rlgl.DisableFramebuffer();
        }

        // Upload the light for the scene pass (after DrawShadowMap, before DrawMesh).
        public void SetLight(ShadowLight light, Vector3 ambient)
        {
            Raylib.SetShaderValueMatrix(Shader, Raylib.GetShaderLocation(Shader, "uShadowMatrix"), Matrix4x4.Transpose(Shadows.LightMatrix(light)));
            Set("uShadowNormalBias", light.NormalBias);
            Set("uShadowBias", light.Bias);
            Set("uShadowRadius", light.Radius);
            Set("uShadowMapSize", (float)_size);
            Set("uAmbient", ambient);
            Set("uLightColor", light.Color * light.Intensity);
            Set("uLightDir", Vector3.Normalize(light.Position - light.Target));
        }

        public void DrawMesh(Mesh mesh, Vector3 albedo, Matrix4x4 transform)
        {
            Set("uAlbedo", albedo);
            Raylib.DrawMesh(mesh, _material, transform);
        }

        public void Dispose()
        {
            Rlgl.UnloadFramebuffer(_fbo);
            Rlgl.UnloadTexture(_depthTexture);
            Raylib.UnloadShader(Shader);
            Raylib.UnloadShader(Depth);
        }
    }
}
