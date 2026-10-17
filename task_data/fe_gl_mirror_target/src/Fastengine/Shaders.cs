namespace Fastengine
{
    // The output stage of fastengine's built-in material (core/Fastengine.Core/Three/Shaders.cs, verbatim): ACES Filmic
    // with exposure when uToneMapping is 1, then sRGB encoding unless uLinearOutput is 1. A surface is either a flat
    // linear colour (uColor) or, for the mirror, its reflection texture times uReflectivity (uUseMap 1).
    public static class Shaders
    {
        public const string Vertex = @"#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
uniform mat4 mvp;
out vec2 vUv;
void main() { vUv = vertexTexCoord; gl_Position = mvp * vec4(vertexPosition, 1.0); }";

        public const string Fragment = @"#version 330
in vec2 vUv;
uniform vec3 uColor;
uniform int uUseMap;
uniform sampler2D texture0;
uniform float uReflectivity;
uniform int uToneMapping;
uniform int uLinearOutput;
uniform float uExposure;
out vec4 finalColor;
vec3 toSRGB(vec3 c) {
    return mix(pow(c, vec3(0.41666)) * 1.055 - vec3(0.055), c * 12.92, vec3(lessThanEqual(c, vec3(0.0031308))));
}
vec3 feRRTAndODTFit(vec3 v) {
    vec3 a = v * (v + 0.0245786) - 0.000090537;
    vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081;
    return a / b;
}
vec3 feACES(vec3 color, float exposure) {
    const mat3 ACESInputMat = mat3(vec3(0.59719, 0.07600, 0.02840), vec3(0.35458, 0.90834, 0.13383), vec3(0.04823, 0.01566, 0.83777));
    const mat3 ACESOutputMat = mat3(vec3(1.60475, -0.10208, -0.00327), vec3(-0.53108, 1.10813, -0.07276), vec3(-0.07367, -0.00605, 1.07602));
    color *= exposure / 0.6;
    color = ACESInputMat * color;
    color = feRRTAndODTFit(color);
    color = ACESOutputMat * color;
    return clamp(color, 0.0, 1.0);
}
void main() {
    vec3 outgoing = uUseMap == 1 ? texture(texture0, vUv).rgb * uReflectivity : uColor;
    if (uToneMapping == 1) outgoing = feACES(outgoing, uExposure);
    vec3 colour = uLinearOutput == 1 ? outgoing : toSRGB(outgoing);
    finalColor = vec4(colour, 1.0);
}";
    }
}
