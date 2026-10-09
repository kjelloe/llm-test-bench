using System;
using System.Collections.Generic;
using System.Linq;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    // Unity draws a triangle's front where its vertices run clockwise, which in Unity's
    // left-handed axes is the side Cross(b - a, c - a) points to. Every face must point out.
    public class MeshesTests
    {
        public static IEnumerable<object[]> All() => new[]
        {
            new object[] { "box" }, new object[] { "sphere" }, new object[] { "icosahedron" },
            new object[] { "cylinder" }, new object[] { "cone" }, new object[] { "frustum" }, new object[] { "torus" },
        };

        static Mesh Make(string name) => name switch
        {
            "box" => Meshes.Box(),
            "sphere" => Meshes.Sphere(10, 8),
            "icosahedron" => Meshes.Icosahedron(),
            "cylinder" => Meshes.Cylinder(1.6f, 1.6f, 22, 6),
            "cone" => Meshes.Cylinder(0, 13, 30, 3),
            "frustum" => Meshes.Cylinder(2.2f, 3.6f, 22, 5),
            "torus" => Meshes.Torus(6, 0.8f, 5, 12),
            _ => throw new ArgumentException(name),
        };

        // Which way is "out" at a point on the surface.
        static Vector3 Outward(string name, Vector3 p)
        {
            if (name != "torus") return p;
            Vector3 flat = new Vector3(p.x, 0, p.z);
            return p - flat.normalized * 6;
        }

        static (Vector3 a, Vector3 b, Vector3 c, int ia, int ib, int ic)[] Triangles(Mesh m)
        {
            Vector3[] v = m.vertices;
            int[] t = m.triangles;
            return Enumerable.Range(0, t.Length / 3).Select(i => (v[t[3 * i]], v[t[3 * i + 1]], v[t[3 * i + 2]], t[3 * i], t[3 * i + 1], t[3 * i + 2])).ToArray();
        }

        static (int, int, int) Key(Vector3 p) => ((int)Math.Round(p.x * 1e4), (int)Math.Round(p.y * 1e4), (int)Math.Round(p.z * 1e4));

        [Theory]
        [MemberData(nameof(All))]
        public void EveryTriangle_FacesOutward(string name)
        {
            Mesh m = Make(name);
            Assert.NotEmpty(m.triangles);
            foreach (var (a, b, c, _, _, _) in Triangles(m))
            {
                Vector3 n = Vector3.Cross(b - a, c - a);
                Vector3 centre = (a + b + c) / 3;
                Assert.True(Vector3.Dot(n, Outward(name, centre)) > 0, $"{name}: triangle {a} {b} {c} faces inward");
            }
        }

        [Theory]
        [MemberData(nameof(All))]
        public void Surface_IsClosed_AndConsistentlyWound(string name)
        {
            // Each edge (by position) is used once in each direction: no holes, no flipped neighbours.
            var directed = new Dictionary<((int, int, int), (int, int, int)), int>();
            foreach (var (a, b, c, _, _, _) in Triangles(Make(name)))
            {
                Assert.True(Vector3.Cross(b - a, c - a).magnitude > 1e-6f, $"{name}: degenerate triangle {a} {b} {c}");
                foreach (var (p, q) in new[] { (a, b), (b, c), (c, a) })
                {
                    var k = (Key(p), Key(q));
                    directed[k] = directed.TryGetValue(k, out int n) ? n + 1 : 1;
                }
            }
            foreach (var kv in directed)
            {
                Assert.True(kv.Value == 1, $"{name}: edge {kv.Key} is used {kv.Value} times in the same direction");
                Assert.True(directed.ContainsKey((kv.Key.Item2, kv.Key.Item1)), $"{name}: edge {kv.Key} has no opposite edge (hole)");
            }
        }

        [Theory]
        [MemberData(nameof(All))]
        public void Normals_AreFlat_AndMatchTheFace(string name)
        {
            Mesh m = Make(name);
            Vector3[] normals = m.normals;
            Assert.Equal(m.vertexCount, normals.Length);
            foreach (var (a, b, c, ia, ib, ic) in Triangles(m))
            {
                Vector3 face = Vector3.Cross(b - a, c - a).normalized;
                foreach (int i in new[] { ia, ib, ic })
                    Assert.True(Vector3.Dot(normals[i], face) > 0.999f, $"{name}: vertex {i} normal {normals[i]} is not the face normal {face} (smooth or flipped)");
            }
        }

        [Fact]
        public void Box_IsAUnitCube()
        {
            Mesh m = Meshes.Box();
            Assert.Equal(12, m.triangles.Length / 3);
            var corners = m.vertices.Select(Key).Distinct().ToArray();
            Assert.Equal(8, corners.Length);
            Assert.All(m.vertices, v => Assert.True(Math.Abs(Math.Abs(v.x) - 0.5f) < 1e-5 && Math.Abs(Math.Abs(v.y) - 0.5f) < 1e-5 && Math.Abs(Math.Abs(v.z) - 0.5f) < 1e-5, v.ToString()));
        }

        [Fact]
        public void Sphere_HasDiameterOne_AndBothPoles()
        {
            Mesh m = Meshes.Sphere(10, 8);
            Assert.All(m.vertices, v => Assert.True(Math.Abs(v.magnitude - 0.5f) < 1e-4, v.ToString()));
            Assert.Contains(m.vertices, v => Math.Abs(v.y - 0.5f) < 1e-5);
            Assert.Contains(m.vertices, v => Math.Abs(v.y + 0.5f) < 1e-5);
            Assert.Equal(2 + 10 * 7, m.vertices.Select(Key).Distinct().Count());
        }

        [Fact]
        public void Icosahedron_HasTwelveCornersAtRadiusOne_AndTwentyFaces()
        {
            Mesh m = Meshes.Icosahedron();
            Assert.Equal(20, m.triangles.Length / 3);
            Assert.Equal(12, m.vertices.Select(Key).Distinct().Count());
            Assert.All(m.vertices, v => Assert.True(Math.Abs(v.magnitude - 1) < 1e-4, v.ToString()));
        }

        [Theory]
        [InlineData(1.6f, 1.6f, 22, 6)]
        [InlineData(0, 13, 30, 3)]
        [InlineData(2.2f, 3.6f, 22, 5)]
        public void Cylinder_HasTheRequestedRadiiHeightAndSides(float top, float bottom, float height, int segments)
        {
            Mesh m = Meshes.Cylinder(top, bottom, height, segments);
            Vector3[] v = m.vertices;
            Assert.All(v, p => Assert.True(Math.Abs(Math.Abs(p.y) - height / 2) < 1e-4, p.ToString()));
            float Radius(Vector3 p) => new Vector2(p.x, p.z).magnitude;
            var topRim = v.Where(p => p.y > 0 && Radius(p) > 1e-4).Select(Key).Distinct().ToArray();
            var bottomRim = v.Where(p => p.y < 0 && Radius(p) > 1e-4).Select(Key).Distinct().ToArray();
            Assert.Equal(top > 0 ? segments : 0, topRim.Length);
            Assert.Equal(segments, bottomRim.Length);
            Assert.All(v.Where(p => Radius(p) > 1e-4), p => Assert.True(Math.Abs(Radius(p) - (p.y > 0 ? top : bottom)) < 1e-4, p.ToString()));
        }

        [Fact]
        public void Torus_LiesAroundTheYAxis_AtTubeDistanceFromItsRing()
        {
            Mesh m = Meshes.Torus(6, 0.8f, 5, 12);
            foreach (Vector3 p in m.vertices)
            {
                Vector3 flat = new Vector3(p.x, 0, p.z);
                Assert.True(Math.Abs((p - flat.normalized * 6).magnitude - 0.8f) < 1e-4, p.ToString());
            }
            Assert.Equal(5 * 12, m.vertices.Select(Key).Distinct().Count());
        }
    }
}
