using UnityEngine;

namespace GameClient
{
    // three.js BoxGeometry / CylinderGeometry / ConeGeometry vertex positions, computed with
    // three.js's own formulas and used as-is in Unity: the same numbers, now read in Unity's
    // axes. A cylinder runs along +Y, centred on the origin; rim vertex k of n sits at angle
    // 2*PI*k/n as (r*sin, y, r*cos). A cone is a cylinder with radiusTop 0.
    public static class Primitives
    {
        public static Mesh Box(float width, float height, float depth)
        {
            var v = new Vector3[8];
            for (int i = 0; i < 8; i++)
                v[i] = new Vector3(((i & 1) == 0 ? -0.5f : 0.5f) * width, ((i & 2) == 0 ? -0.5f : 0.5f) * height, ((i & 4) == 0 ? -0.5f : 0.5f) * depth);
            return new Mesh { name = "Box", vertices = v };
        }

        public static Mesh Cylinder(float radiusTop, float radiusBottom, float height, int radialSegments)
        {
            var v = new Vector3[2 * radialSegments + 2];
            for (int k = 0; k < radialSegments; k++)
            {
                float a = 2 * Mathf.PI * k / radialSegments;
                v[k] = new Vector3(radiusTop * Mathf.Sin(a), height / 2, radiusTop * Mathf.Cos(a));
                v[radialSegments + k] = new Vector3(radiusBottom * Mathf.Sin(a), -height / 2, radiusBottom * Mathf.Cos(a));
            }
            v[2 * radialSegments] = new Vector3(0, height / 2, 0);
            v[2 * radialSegments + 1] = new Vector3(0, -height / 2, 0);
            return new Mesh { name = "Cylinder", vertices = v };
        }

        public static Mesh Cone(float radius, float height, int radialSegments) => Cylinder(0, radius, height, radialSegments);
    }
}
