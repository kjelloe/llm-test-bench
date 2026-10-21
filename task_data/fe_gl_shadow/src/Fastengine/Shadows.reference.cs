using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // Reference: fastengine's Renderer.ShadowPass (core/Fastengine.Core/Three/Renderer.cs) and shadowPcf/shadowMask
    // (Three/Shaders.cs), fastengine 6ae4ed8.
    // The shadow-map half of fastengine's port of three r162's WebGLShadowMap (PCFShadowMap, the browser game's
    // renderer.shadowMap.type) for one directional light. ShadowRenderer (not editable) calls these: it draws the
    // casters into a depth texture with LightMatrix as the camera, then draws the scene with Glsl's shadowMask()
    // scaling the light's direct term.
    public static class Shadows
    {
        // The light's view-projection, in System.Numerics' row-vector order (ShadowRenderer transposes it for GL). The
        // depth pass renders with it, and the scene shader computes shadowCoord = uShadowMatrix * world position (moved
        // along the normal by normalBias) with it.
        public static Matrix4x4 LightMatrix(ShadowLight light)
        {
            var view = Matrix4x4.CreateLookAt(light.Position, light.Target, Vector3.UnitY);
            // three's OrthographicCamera.projectionMatrix: GL clip z (-1..1, where System.Numerics' runs 0..1), so the
            // stored depth runs 0..1 from near to far and shadow.bias is in three's units.
            var projection = Matrix4x4.CreateOrthographicOffCenter(light.Left, light.Right, light.Bottom, light.Top, light.Near, light.Far);
            projection.M33 = -2 / (light.Far - light.Near);
            projection.M43 = -(light.Far + light.Near) / (light.Far - light.Near);
            return view * projection;
        }

        // Face culling for the depth pass (Rlgl.SetCullFace: 0 = cull front faces, 1 = cull back faces). Casters use
        // three's default FrontSide material.
        // three's shadowSide: a FrontSide caster draws its back faces into the map.
        public static void CullForDepthPass() => Rlgl.SetCullFace(0);

        // Included in the scene's fragment shader. texture1 is the depth map (depth 0..1 in .r, nearest filtering,
        // clamped to edge); ShadowRenderer sets uShadowBias, uShadowRadius and uShadowMapSize from the light.
        // Returns 1 for lit, 0 for fully shadowed.
        public const string Glsl = @"
uniform sampler2D texture1;
uniform float uShadowBias;
uniform float uShadowRadius;
uniform float uShadowMapSize;
float shadowCompare(vec2 uv, float z) { return step(z, texture(texture1, uv).r); }
float shadowPcf(vec2 xy, float z) {
    vec2 texelSize = vec2(1.0) / uShadowMapSize;
    float dx0 = -texelSize.x * uShadowRadius;
    float dy0 = -texelSize.y * uShadowRadius;
    float dx1 = texelSize.x * uShadowRadius;
    float dy1 = texelSize.y * uShadowRadius;
    float dx2 = dx0 / 2.0;
    float dy2 = dy0 / 2.0;
    float dx3 = dx1 / 2.0;
    float dy3 = dy1 / 2.0;
    return (
        shadowCompare(xy + vec2(dx0, dy0), z) +
        shadowCompare(xy + vec2(0.0, dy0), z) +
        shadowCompare(xy + vec2(dx1, dy0), z) +
        shadowCompare(xy + vec2(dx2, dy2), z) +
        shadowCompare(xy + vec2(0.0, dy2), z) +
        shadowCompare(xy + vec2(dx3, dy2), z) +
        shadowCompare(xy + vec2(dx0, 0.0), z) +
        shadowCompare(xy + vec2(dx2, 0.0), z) +
        shadowCompare(xy, z) +
        shadowCompare(xy + vec2(dx3, 0.0), z) +
        shadowCompare(xy + vec2(dx1, 0.0), z) +
        shadowCompare(xy + vec2(dx2, dy3), z) +
        shadowCompare(xy + vec2(0.0, dy3), z) +
        shadowCompare(xy + vec2(dx3, dy3), z) +
        shadowCompare(xy + vec2(dx0, dy1), z) +
        shadowCompare(xy + vec2(0.0, dy1), z) +
        shadowCompare(xy + vec2(dx1, dy1), z)
    ) * (1.0 / 17.0);
}
// three r162's getShadow: outside the shadow camera nothing is shadowed.
float shadowMask(vec4 shadowCoord) {
    vec3 c = shadowCoord.xyz / shadowCoord.w;
    c = c * 0.5 + 0.5;
    float z = c.z + uShadowBias;
    if (c.x < 0.0 || c.x > 1.0 || c.y < 0.0 || c.y > 1.0 || z > 1.0) return 1.0;
    return shadowPcf(c.xy, z);
}";
    }
}
