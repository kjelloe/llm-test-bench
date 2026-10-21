using System;
using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // MeshLambertMaterial on raylib (GLSL 330): the shader and the per-frame light upload. A surface's normal arrives in
    // world space as the uniform uNormal (the test draws flat quads); its colour as the material's hex.
    public static class Lambert
    {
        public const string Vertex = @"#version 330
in vec3 vertexPosition;
uniform mat4 mvp;
void main() { gl_Position = mvp * vec4(vertexPosition, 1.0); }";

        public const string Fragment = @"#version 330
uniform vec3 uNormal;
uniform vec3 uAlbedo;
uniform vec3 uAmbient;
uniform int uDirCount;
uniform vec3 uDirColor[4];
uniform vec3 uDirDir[4];
out vec4 finalColor;
void main() {
    vec3 n = normalize(uNormal);
    vec3 light = uAmbient;
    for (int i = 0; i < uDirCount; i++) light += uDirColor[i] * dot(n, uDirDir[i]);
    finalColor = vec4(uAlbedo * light, 1.0);
}";

        static Vector3 Rgb(int hex) => new Vector3((hex >> 16) & 255, (hex >> 8) & 255, hex & 255) / 255f;

        static void Set(Shader s, string name, Vector3 v) => Raylib.SetShaderValue(s, Raylib.GetShaderLocation(s, name), v, ShaderUniformDataType.Vec3);

        // Upload the scene's lights and the material colour before drawing with the shader.
        public static void Apply(Shader shader, IEnumerable<Light> lights, int materialHex)
        {
            var ambient = Vector3.Zero;
            var count = 0;
            foreach (var light in lights)
            {
                if (light is AmbientLight) ambient += Rgb(light.Hex) * light.Intensity;
                else if (light is DirectionalLight d && count < 4)
                {
                    Set(shader, $"uDirColor[{count}]", Rgb(d.Hex) * d.Intensity);
                    Set(shader, $"uDirDir[{count}]", Vector3.Normalize(d.Target - d.Position));
                    count++;
                }
            }
            Set(shader, "uAmbient", ambient);
            Raylib.SetShaderValue(shader, Raylib.GetShaderLocation(shader, "uDirCount"), count, ShaderUniformDataType.Int);
            Set(shader, "uAlbedo", Rgb(materialHex));
        }
    }
}
