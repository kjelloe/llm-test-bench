using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
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
            var projection = Matrix4x4.CreateOrthographicOffCenter(light.Left, light.Right, light.Bottom, light.Top, light.Near, light.Far);
            return projection * view;
        }

        // Face culling for the depth pass (Rlgl.SetCullFace: 0 = cull front faces, 1 = cull back faces). Casters use
        // three's default FrontSide material.
        public static void CullForDepthPass() => Rlgl.SetCullFace(1);

        // Included in the scene's fragment shader. texture1 is the depth map (depth 0..1 in .r, nearest filtering,
        // clamped to edge); ShadowRenderer sets uShadowBias, uShadowRadius and uShadowMapSize from the light.
        // Returns 1 for lit, 0 for fully shadowed.
        public const string Glsl = @"
uniform sampler2D texture1;
uniform float uShadowBias;
uniform float uShadowRadius;
uniform float uShadowMapSize;
float shadowMask(vec4 shadowCoord) {
    vec3 c = shadowCoord.xyz / shadowCoord.w * 0.5 + 0.5;
    c.y = 1.0 - c.y;
    return step(c.z, texture(texture1, c.xy).r);
}";
    }
}
