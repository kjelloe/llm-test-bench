using System.Text.RegularExpressions;

namespace Fastengine
{
    // fastengine's ShaderMaterial port (core/Fastengine.Core/Three/Shaders.cs, verbatim but for its custom-attribute
    // step, which is Instancing.Attributes' job here): a browser three.js shader's GLSL (WebGL 1/2 style, three's built-in
    // names) as GLSL 330 for raylib. A declaration `attribute vec3 aSeed;` that reaches it stays an ordinary `in vec3 aSeed;`.
    // Not editable.
    public static class ShaderPort
    {
        // three's ShaderMaterial GLSL (WebGL 1/2 style) as GLSL 330: its built-in attributes and uniforms are
        // raylib's under three's names, and gl_FragColor an output. Precision qualifiers are dropped.
        const string Common = @"#define texture2D texture
#define modelMatrix matModel
#define viewMatrix matView
#define projectionMatrix matProjection
#define modelViewMatrix (matView * matModel)
uniform mat4 matModel;
uniform mat4 matView;
uniform mat4 matProjection;
uniform vec3 cameraPosition;
";

        public static string WrapVertex(string glsl) => "#version 330\n#define attribute in\n#define varying out\n" + Common +
            "in vec3 vertexPosition;\nin vec3 vertexNormal;\nin vec2 vertexTexCoord;\n#define position vertexPosition\n#define normal vertexNormal\n#define uv vertexTexCoord\n" +
            "#define normalMatrix mat3(transpose(inverse(matView * matModel)))\n" + Chunks(Strip(glsl), true);

        public static string WrapFragment(string glsl) => "#version 330\n#define varying in\n#define gl_FragColor feFragColor\nout vec4 feFragColor;\n" + Common +
            Chunks(Strip(glsl), false);

        // three's shader chunks as far as the vendored shaders use them: output tone mapping (ACES, by the
        // renderer's setting) and sRGB encoding, FogExp2 and linear Fog (by which uniforms the scene's fog fills), and a
        // shadow mask of 1 (the mirror receives none).
        // Anything else included is empty.
        static string Chunks(string glsl, bool vertex) =>
            Regex.Replace(glsl, @"#include\s*<(\w+)>", m => m.Groups[1].Value switch
            {
                "common" => "#define PI 3.141592653589793\n#define saturate(a) clamp(a, 0.0, 1.0)\n",
                "fog_pars_vertex" => "varying float vFogDepth;\n",
                "fog_vertex" => "vFogDepth = -mvPosition.z;\n",
                "fog_pars_fragment" => "uniform vec3 fogColor;\nuniform float fogDensity;\nuniform float fogNear;\nuniform float fogFar;\nvarying float vFogDepth;\n",
                "fog_fragment" => "if (fogDensity > 0.0) gl_FragColor.rgb = mix(gl_FragColor.rgb, fogColor, clamp(1.0 - exp(-fogDensity * fogDensity * vFogDepth * vFogDepth), 0.0, 1.0));\n"
                    + "else if (fogFar > fogNear) gl_FragColor.rgb = mix(gl_FragColor.rgb, fogColor, smoothstep(fogNear, fogFar, vFogDepth));\n",
                "shadowmask_pars_fragment" => "float getShadowMask() { return 1.0; }\n",
                "tonemapping_fragment" => "if (feToneMapping == 1) gl_FragColor.rgb = feACES(gl_FragColor.rgb, toneMappingExposure);\n",
                "colorspace_fragment" => "if (feLinearOutput == 0) gl_FragColor.rgb = mix(pow(gl_FragColor.rgb, vec3(0.41666)) * 1.055 - vec3(0.055), gl_FragColor.rgb * 12.92, vec3(lessThanEqual(gl_FragColor.rgb, vec3(0.0031308))));\n",
                _ => "",
            }) is var body && !vertex ? "uniform int feToneMapping;\nuniform int feLinearOutput;\nuniform float toneMappingExposure;\n" + Aces + body : body;

        const string Aces = @"vec3 feRRTAndODTFit(vec3 v) {
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
";

        static string Strip(string glsl) =>
            Regex.Replace(glsl, @"^\s*precision\s+\w+\s+\w+\s*;", "", RegexOptions.Multiline);
    }
}
