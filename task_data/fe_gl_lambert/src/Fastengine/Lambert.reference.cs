using System;
using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // MeshLambertMaterial on raylib (GLSL 330): the shader and the per-frame light upload. A surface's normal arrives in
    // world space as the uniform uNormal (the test draws flat quads); its colour as the material's hex.
    // Reference: fastengine's lambert path (core/Fastengine.Core/Three/Shaders.cs, Renderer.cs light upload, Color.cs).
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
uniform vec3 uHemiSky;
uniform vec3 uHemiGround;
uniform int uDirCount;
uniform vec3 uDirColor[4];
uniform vec3 uDirDir[4];
out vec4 finalColor;
vec3 toSRGB(vec3 c) {
    return mix(pow(c, vec3(0.41666)) * 1.055 - vec3(0.055), c * 12.92, vec3(lessThanEqual(c, vec3(0.0031308))));
}
void main() {
    vec3 n = normalize(uNormal);
    vec3 irradiance = uAmbient + mix(uHemiGround, uHemiSky, n.y * 0.5 + 0.5);
    for (int i = 0; i < uDirCount; i++) irradiance += uDirColor[i] * max(dot(n, uDirDir[i]), 0.0);
    vec3 outgoing = uAlbedo * irradiance * 0.3183098861837907;
    finalColor = vec4(toSRGB(clamp(outgoing, 0.0, 1.0)), 1.0);
}";

        static float ToLinear(int channel)
        {
            var c = channel / 255f;
            return c < 0.04045f ? c * 0.0773993808f : MathF.Pow(c * 0.9478672986f + 0.0521327014f, 2.4f);
        }

        static Vector3 Rgb(int hex) => new Vector3(ToLinear((hex >> 16) & 255), ToLinear((hex >> 8) & 255), ToLinear(hex & 255));

        static void Set(Shader s, string name, Vector3 v) => Raylib.SetShaderValue(s, Raylib.GetShaderLocation(s, name), v, ShaderUniformDataType.Vec3);

        // Upload the scene's lights and the material colour before drawing with the shader.
        public static void Apply(Shader shader, IEnumerable<Light> lights, int materialHex)
        {
            Vector3 ambient = Vector3.Zero, sky = Vector3.Zero, ground = Vector3.Zero;
            var count = 0;
            foreach (var light in lights)
            {
                if (light is AmbientLight) ambient += Rgb(light.Hex) * light.Intensity;
                else if (light is HemisphereLight h)
                {
                    sky += Rgb(h.Hex) * h.Intensity;
                    ground += Rgb(h.GroundHex) * h.Intensity;
                }
                else if (light is DirectionalLight d && count < 4)
                {
                    Set(shader, $"uDirColor[{count}]", Rgb(d.Hex) * d.Intensity);
                    Set(shader, $"uDirDir[{count}]", Vector3.Normalize(d.Position - d.Target));
                    count++;
                }
            }
            Set(shader, "uAmbient", ambient);
            Set(shader, "uHemiSky", sky);
            Set(shader, "uHemiGround", ground);
            Raylib.SetShaderValue(shader, Raylib.GetShaderLocation(shader, "uDirCount"), count, ShaderUniformDataType.Int);
            Set(shader, "uAlbedo", Rgb(materialHex));
        }
    }
}
