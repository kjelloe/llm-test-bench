using System;
using System.Collections.Generic;

namespace Fastengine.Three
{
    public sealed class GeometryData
    {
        public float[] Positions;
        public float[] Normals;
        public float[] Uvs;
        public int[] Indices;
    }

    public static class Geometries
    {
        sealed class Builder
        {
            public readonly List<float> P = new(), N = new(), U = new();
            public readonly List<int> I = new();
            public int Count => P.Count / 3;
            public void V(float x, float y, float z) { P.Add(x); P.Add(y); P.Add(z); }
            public void Nrm(float x, float y, float z) { N.Add(x); N.Add(y); N.Add(z); }
            public void Uv(float u, float v) { U.Add(u); U.Add(v); }
            public void Tri(int a, int b, int c) { I.Add(a); I.Add(b); I.Add(c); }
            public GeometryData Done() => new() { Positions = P.ToArray(), Normals = N.ToArray(), Uvs = U.ToArray(), Indices = I.ToArray() };
        }

        public static GeometryData Box(float width = 1, float height = 1, float depth = 1,
            int widthSegments = 1, int heightSegments = 1, int depthSegments = 1)
        {
            var b = new Builder();
            // three's buildPlane(u, v, w, udir, vdir, width, height, depth, gridX, gridY); axes 0=x 1=y 2=z
            void Plane(int u, int v, int w, float udir, float vdir, float pw, float ph, float pd, int gx, int gy)
            {
                float segW = pw / gx, segH = ph / gy, halfW = pw / 2, halfH = ph / 2, depthHalf = pd / 2;
                int gx1 = gx + 1, gy1 = gy + 1, start = b.Count;
                var vec = new float[3];
                for (int iy = 0; iy < gy1; iy++)
                {
                    float y = iy * segH - halfH;
                    for (int ix = 0; ix < gx1; ix++)
                    {
                        float x = ix * segW - halfW;
                        vec[u] = x * udir; vec[v] = y * vdir; vec[w] = depthHalf;
                        b.V(vec[0], vec[1], vec[2]);
                        vec[u] = 0; vec[v] = 0; vec[w] = pd > 0 ? 1 : -1;
                        b.Nrm(vec[0], vec[1], vec[2]);
                        b.Uv((float)ix / gx, 1 - (float)iy / gy);
                    }
                }
                for (int iy = 0; iy < gy; iy++)
                    for (int ix = 0; ix < gx; ix++)
                    {
                        int a = start + ix + gx1 * iy, bb = start + ix + gx1 * (iy + 1);
                        int c = start + (ix + 1) + gx1 * (iy + 1), d = start + (ix + 1) + gx1 * iy;
                        b.Tri(a, bb, d);
                        b.Tri(bb, c, d);
                    }
            }
            Plane(2, 1, 0, -1, -1, depth, height, width, depthSegments, heightSegments);   // px
            Plane(2, 1, 0, 1, -1, depth, height, -width, depthSegments, heightSegments);   // nx
            Plane(0, 2, 1, 1, 1, width, depth, height, widthSegments, depthSegments);      // py
            Plane(0, 2, 1, 1, -1, width, depth, -height, widthSegments, depthSegments);    // ny
            Plane(0, 1, 2, 1, -1, width, height, depth, widthSegments, heightSegments);    // pz
            Plane(0, 1, 2, -1, -1, width, height, -depth, widthSegments, heightSegments);  // nz
            return b.Done();
        }

        public static GeometryData Cylinder(float radiusTop = 1, float radiusBottom = 1, float height = 1,
            int radialSegments = 32, int heightSegments = 1, bool openEnded = false,
            float thetaStart = 0, float thetaLength = MathF.PI * 2)
        {
            var b = new Builder();
            float halfHeight = height / 2;
            var indexArray = new List<int[]>();
            float slope = (radiusBottom - radiusTop) / height;
            for (int y = 0; y <= heightSegments; y++)
            {
                var row = new int[radialSegments + 1];
                float v = (float)y / heightSegments;
                float radius = v * (radiusBottom - radiusTop) + radiusTop;
                for (int x = 0; x <= radialSegments; x++)
                {
                    float u = (float)x / radialSegments;
                    float theta = u * thetaLength + thetaStart;
                    float sinTheta = MathF.Sin(theta), cosTheta = MathF.Cos(theta);
                    b.V(radius * sinTheta, -v * height + halfHeight, radius * cosTheta);
                    float nx = sinTheta, ny = slope, nz = cosTheta, len = MathF.Sqrt(nx * nx + ny * ny + nz * nz);
                    if (len == 0) len = 1;
                    b.Nrm(nx / len, ny / len, nz / len);
                    b.Uv(u, 1 - v);
                    row[x] = b.Count - 1;
                }
                indexArray.Add(row);
            }
            for (int x = 0; x < radialSegments; x++)
                for (int y = 0; y < heightSegments; y++)
                {
                    int a = indexArray[y][x], bb = indexArray[y + 1][x], c = indexArray[y + 1][x + 1], d = indexArray[y][x + 1];
                    b.Tri(a, bb, d);   // three 0.165 keeps the degenerate triangles at a cone's tip
                    b.Tri(bb, c, d);
                }
            if (!openEnded)
            {
                if (radiusTop > 0) Cap(true);
                if (radiusBottom > 0) Cap(false);
            }
            return b.Done();

            void Cap(bool top)
            {
                float radius = top ? radiusTop : radiusBottom, sign = top ? 1 : -1;
                int centerIndexStart = b.Count;
                for (int x = 1; x <= radialSegments; x++)
                {
                    b.V(0, halfHeight * sign, 0);
                    b.Nrm(0, sign, 0);
                    b.Uv(0.5f, 0.5f);
                }
                int centerIndexEnd = b.Count;
                for (int x = 0; x <= radialSegments; x++)
                {
                    float u = (float)x / radialSegments;
                    float theta = u * thetaLength + thetaStart;
                    float cosTheta = MathF.Cos(theta), sinTheta = MathF.Sin(theta);
                    b.V(radius * sinTheta, halfHeight * sign, radius * cosTheta);
                    b.Nrm(0, sign, 0);
                    b.Uv(cosTheta * 0.5f + 0.5f, sinTheta * 0.5f * sign + 0.5f);
                }
                for (int x = 0; x < radialSegments; x++)
                {
                    int c = centerIndexStart + x, i = centerIndexEnd + x;
                    if (top) b.Tri(i, i + 1, c);
                    else b.Tri(i + 1, i, c);
                }
            }
        }

        public static GeometryData Cone(float radius = 1, float height = 1, int radialSegments = 32,
            int heightSegments = 1, bool openEnded = false, float thetaStart = 0, float thetaLength = MathF.PI * 2)
            => Cylinder(0, radius, height, radialSegments, heightSegments, openEnded, thetaStart, thetaLength);

        public static GeometryData Sphere(float radius = 1, int widthSegments = 32, int heightSegments = 16,
            float phiStart = 0, float phiLength = MathF.PI * 2, float thetaStart = 0, float thetaLength = MathF.PI)
        {
            widthSegments = Math.Max(3, widthSegments);
            heightSegments = Math.Max(2, heightSegments);
            float thetaEnd = MathF.Min(thetaStart + thetaLength, MathF.PI);
            var b = new Builder();
            var grid = new List<int[]>();
            int index = 0;
            for (int iy = 0; iy <= heightSegments; iy++)
            {
                var row = new int[widthSegments + 1];
                float v = (float)iy / heightSegments;
                float uOffset = 0;
                if (iy == 0 && thetaStart == 0) uOffset = 0.5f / widthSegments;
                else if (iy == heightSegments && thetaEnd == MathF.PI) uOffset = -0.5f / widthSegments;
                for (int ix = 0; ix <= widthSegments; ix++)
                {
                    float u = (float)ix / widthSegments;
                    float x = -radius * MathF.Cos(phiStart + u * phiLength) * MathF.Sin(thetaStart + v * thetaLength);
                    float y = radius * MathF.Cos(thetaStart + v * thetaLength);
                    float z = radius * MathF.Sin(phiStart + u * phiLength) * MathF.Sin(thetaStart + v * thetaLength);
                    b.V(x, y, z);
                    float len = MathF.Sqrt(x * x + y * y + z * z);
                    if (len == 0) len = 1;
                    b.Nrm(x / len, y / len, z / len);
                    b.Uv(u + uOffset, 1 - v);
                    row[ix] = index++;
                }
                grid.Add(row);
            }
            for (int iy = 0; iy < heightSegments; iy++)
                for (int ix = 0; ix < widthSegments; ix++)
                {
                    int a = grid[iy][ix + 1], bb = grid[iy][ix], c = grid[iy + 1][ix], d = grid[iy + 1][ix + 1];
                    if (iy != 0 || thetaStart > 0) b.Tri(a, bb, d);
                    if (iy != heightSegments - 1 || thetaEnd < MathF.PI) b.Tri(bb, c, d);
                }
            return b.Done();
        }

        public static GeometryData Torus(float radius = 1, float tube = 0.4f, int radialSegments = 12,
            int tubularSegments = 48, float arc = MathF.PI * 2)
        {
            var b = new Builder();
            for (int j = 0; j <= radialSegments; j++)
                for (int i = 0; i <= tubularSegments; i++)
                {
                    float u = (float)i / tubularSegments * arc;
                    float v = (float)j / radialSegments * MathF.PI * 2;
                    float x = (radius + tube * MathF.Cos(v)) * MathF.Cos(u);
                    float y = (radius + tube * MathF.Cos(v)) * MathF.Sin(u);
                    float z = tube * MathF.Sin(v);
                    b.V(x, y, z);
                    float cx = radius * MathF.Cos(u), cy = radius * MathF.Sin(u);
                    float nx = x - cx, ny = y - cy, nz = z, len = MathF.Sqrt(nx * nx + ny * ny + nz * nz);
                    if (len == 0) len = 1;
                    b.Nrm(nx / len, ny / len, nz / len);
                    b.Uv((float)i / tubularSegments, (float)j / radialSegments);
                }
            for (int j = 1; j <= radialSegments; j++)
                for (int i = 1; i <= tubularSegments; i++)
                {
                    int a = (tubularSegments + 1) * j + i - 1, bb = (tubularSegments + 1) * (j - 1) + i - 1;
                    int c = (tubularSegments + 1) * (j - 1) + i, d = (tubularSegments + 1) * j + i;
                    b.Tri(a, bb, d);
                    b.Tri(bb, c, d);
                }
            return b.Done();
        }
    }
}
