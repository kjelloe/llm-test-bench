using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    // Procedural primitives, so views need neither built-in resources nor the
    // physics module that GameObject.CreatePrimitive drags in with colliders.
    public static class Meshes
    {
        public static Mesh Box() => BuildBox();
        public static Mesh Sphere(int segments, int rings) => BuildSphere(segments, rings);
        public static Mesh Icosahedron() => BuildIcosahedron();
        public static Mesh Cylinder(float radiusTop, float radiusBottom, float height, int segments) => BuildCylinder(radiusTop, radiusBottom, height, segments);
        public static Mesh Torus(float radius, float tube, int radialSegments, int tubularSegments) => BuildTorus(radius, tube, radialSegments, tubularSegments);

        static Mesh BuildBox()
        {
            var normals = new[] { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
            var vertices = new Vector3[24];
            var meshNormals = new Vector3[24];
            var triangles = new int[36];
            for (var f = 0; f < 6; f++)
            {
                var n = normals[f];
                var u = new Vector3(n.y, n.z, n.x);
                var v = Vector3.Cross(n, u);
                for (var c = 0; c < 4; c++)
                {
                    var su = c == 1 || c == 2 ? 0.5f : -0.5f;
                    var sv = c >= 2 ? 0.5f : -0.5f;
                    vertices[f * 4 + c] = n * 0.5f + u * su + v * sv;
                    meshNormals[f * 4 + c] = n;
                }
                var b = f * 4;
                var t = f * 6;
                triangles[t] = b; triangles[t + 1] = b + 1; triangles[t + 2] = b + 2;
                triangles[t + 3] = b; triangles[t + 4] = b + 2; triangles[t + 5] = b + 3;
            }
            var mesh = new Mesh { name = "Box", vertices = vertices, normals = meshNormals, triangles = triangles };
            mesh.RecalculateBounds();
            return mesh;
        }

        static Mesh BuildSphere(int segments, int rings)
        {
            Vector3 At(int r, int seg)
            {
                var phi = Mathf.PI * r / rings;
                var theta = 2 * Mathf.PI * seg / segments;
                return 0.5f * new Vector3(Mathf.Sin(phi) * Mathf.Cos(theta), Mathf.Cos(phi), Mathf.Sin(phi) * Mathf.Sin(theta));
            }
            var faces = new List<Vector3[]>();
            for (var r = 0; r < rings; r++)
                for (var seg = 0; seg < segments; seg++)
                {
                    if (r > 0) faces.Add(new[] { At(r, seg), At(r, seg + 1), At(r + 1, seg) });
                    if (r < rings - 1) faces.Add(new[] { At(r, seg + 1), At(r + 1, seg + 1), At(r + 1, seg) });
                }
            return Convex("Sphere", faces);
        }

        static Mesh BuildIcosahedron()
        {
            var t = (1 + Mathf.Sqrt(5)) / 2;
            var v = new[]
            {
                new Vector3(-1, t, 0), new Vector3(1, t, 0), new Vector3(-1, -t, 0), new Vector3(1, -t, 0),
                new Vector3(0, -1, t), new Vector3(0, 1, t), new Vector3(0, -1, -t), new Vector3(0, 1, -t),
                new Vector3(t, 0, -1), new Vector3(t, 0, 1), new Vector3(-t, 0, -1), new Vector3(-t, 0, 1),
            };
            int[] f =
            {
                0, 11, 5, 0, 5, 1, 0, 1, 7, 0, 7, 10, 0, 10, 11, 1, 5, 9, 5, 11, 4, 11, 10, 2, 10, 7, 6, 7, 1, 8,
                3, 9, 4, 3, 4, 2, 3, 2, 6, 3, 6, 8, 3, 8, 9, 4, 9, 5, 2, 4, 11, 6, 2, 10, 8, 6, 7, 9, 8, 1,
            };
            var faces = new List<Vector3[]>();
            for (var i = 0; i < f.Length; i += 3)
                faces.Add(new[] { v[f[i]].normalized, v[f[i + 1]].normalized, v[f[i + 2]].normalized });
            return Convex("Icosahedron", faces);
        }

        // A convex shape around the origin from loose triangles: each is wound
        // so its front faces outward (Unity fronts are clockwise), unshared.
        static Mesh Convex(string name, List<Vector3[]> faces)
        {
            var vertices = new List<Vector3>();
            foreach (var f in faces)
            {
                var outward = Vector3.Dot(Vector3.Cross(f[1] - f[0], f[2] - f[0]), f[0] + f[1] + f[2]) > 0;
                vertices.AddRange(outward ? f : new[] { f[0], f[2], f[1] });
            }
            var triangles = new List<int>();
            for (var i = 0; i < vertices.Count; i++) triangles.Add(i);
            return Finish(name, vertices, triangles);
        }

        static Mesh BuildCylinder(float radiusTop, float radiusBottom, float height, int segments)
        {
            var vertices = new List<Vector3>();
            var triangles = new List<int>();
            var top = height / 2;
            Vector3 Rim(float radius, float y, int s)
            {
                var a = 2 * Mathf.PI * s / segments;
                return new Vector3(radius * Mathf.Sin(a), y, radius * Mathf.Cos(a));
            }
            void Face(params Vector3[] corners)
            {
                var b = vertices.Count;
                vertices.AddRange(corners);
                for (var i = 1; i + 1 < corners.Length; i++) triangles.AddRange(new[] { b, b + i + 1, b + i });
            }
            for (var s = 0; s < segments; s++)
            {
                if (radiusTop > 0)
                    Face(Rim(radiusBottom, -top, s), Rim(radiusTop, top, s), Rim(radiusTop, top, s + 1), Rim(radiusBottom, -top, s + 1));
                else
                    Face(Rim(radiusBottom, -top, s), new Vector3(0, top, 0), Rim(radiusBottom, -top, s + 1));
                if (radiusTop > 0) Face(new Vector3(0, top, 0), Rim(radiusTop, top, s + 1), Rim(radiusTop, top, s));
                Face(new Vector3(0, -top, 0), Rim(radiusBottom, -top, s), Rim(radiusBottom, -top, s + 1));
            }
            return Finish("Cylinder", vertices, triangles);
        }

        static Mesh BuildTorus(float radius, float tube, int radialSegments, int tubularSegments)
        {
            var vertices = new List<Vector3>();
            var triangles = new List<int>();
            Vector3 At(int j, int i)
            {
                var u = 2 * Mathf.PI * i / tubularSegments;
                var v = 2 * Mathf.PI * j / radialSegments;
                var r = radius + tube * Mathf.Cos(v);
                return new Vector3(r * Mathf.Cos(u), tube * Mathf.Sin(v), r * Mathf.Sin(u));
            }
            for (var j = 0; j < radialSegments; j++)
                for (var i = 0; i < tubularSegments; i++)
                {
                    var b = vertices.Count;
                    vertices.AddRange(new[] { At(j, i), At(j + 1, i), At(j + 1, i + 1), At(j, i + 1) });
                    triangles.AddRange(new[] { b, b + 1, b + 2, b, b + 2, b + 3 });
                }
            return Finish("Torus", vertices, triangles);
        }

        // Unshared vertices per face, so normals come out flat.
        static Mesh Finish(string name, List<Vector3> vertices, List<int> triangles)
        {
            var mesh = new Mesh { name = name, vertices = vertices.ToArray(), triangles = triangles.ToArray() };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
