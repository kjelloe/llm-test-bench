using System;

namespace Fastengine.Three
{
    // CPU geometry for the renderer: flat arrays laid out exactly like three's BufferGeometry attributes
    // (position and normal: 3 floats per vertex, uv: 2 per vertex, index: 3 per triangle).
    public sealed class GeometryData
    {
        public float[] Positions;
        public float[] Normals;
        public float[] Uvs;
        public int[] Indices;
    }

    // three.js r162+ geometries, ported so that every vertex, normal, uv and index matches what three builds
    // for the same parameters (js/three/*.js are three's own sources). Defaults are three's defaults.
    public static class Geometries
    {
        public static GeometryData Box(float width = 1, float height = 1, float depth = 1,
            int widthSegments = 1, int heightSegments = 1, int depthSegments = 1)
            => throw new NotImplementedException();

        public static GeometryData Cylinder(float radiusTop = 1, float radiusBottom = 1, float height = 1,
            int radialSegments = 32, int heightSegments = 1, bool openEnded = false,
            float thetaStart = 0, float thetaLength = MathF.PI * 2)
            => throw new NotImplementedException();

        public static GeometryData Cone(float radius = 1, float height = 1, int radialSegments = 32,
            int heightSegments = 1, bool openEnded = false, float thetaStart = 0, float thetaLength = MathF.PI * 2)
            => throw new NotImplementedException();

        public static GeometryData Sphere(float radius = 1, int widthSegments = 32, int heightSegments = 16,
            float phiStart = 0, float phiLength = MathF.PI * 2, float thetaStart = 0, float thetaLength = MathF.PI)
            => throw new NotImplementedException();

        public static GeometryData Torus(float radius = 1, float tube = 0.4f, int radialSegments = 12,
            int tubularSegments = 48, float arc = MathF.PI * 2)
            => throw new NotImplementedException();
    }
}
