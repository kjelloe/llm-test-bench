using System;
using System.Collections.Generic;
using System.Linq;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    // Expected positions come from three.js's own math, in doubles: the geometry operations in
    // order, then the mesh's matrix (scale, Euler XYZ rotation, position), then z mirrored into
    // Unity's axes. The port is checked by where every vertex of its primitive actually lands.
    public class PartPortTests
    {
        struct V
        {
            public double X, Y, Z;
            public V(double x, double y, double z) { X = x; Y = y; Z = z; }
            public static V operator +(V a, V b) => new V(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        }

        static Func<V, V> RotX(double t) => v => new V(v.X, v.Y * Math.Cos(t) - v.Z * Math.Sin(t), v.Y * Math.Sin(t) + v.Z * Math.Cos(t));
        static Func<V, V> RotY(double t) => v => new V(v.X * Math.Cos(t) + v.Z * Math.Sin(t), v.Y, -v.X * Math.Sin(t) + v.Z * Math.Cos(t));
        static Func<V, V> RotZ(double t) => v => new V(v.X * Math.Cos(t) - v.Y * Math.Sin(t), v.X * Math.Sin(t) + v.Y * Math.Cos(t), v.Z);
        static Func<V, V> Scale(double x, double y, double z) => v => new V(v.X * x, v.Y * y, v.Z * z);

        sealed class ThreePart
        {
            public Mesh Mesh;
            public Func<V, V>[] Geometry = new Func<V, V>[0];
            public V Rotation, MeshScale = new V(1, 1, 1), Position;

            public V[] World()
            {
                return Mesh.vertices.Select(p =>
                {
                    var v = new V(p.x, p.y, p.z);
                    foreach (var op in Geometry) v = op(v);
                    v = Scale(MeshScale.X, MeshScale.Y, MeshScale.Z)(v);
                    v = RotX(Rotation.X)(RotY(Rotation.Y)(RotZ(Rotation.Z)(v))); // Euler order 'XYZ'
                    v += Position;
                    return new V(v.X, v.Y, -v.Z);
                }).ToArray();
            }
        }

        static readonly Dictionary<string, (Func<Transform, Transform> port, ThreePart three)> Parts = new Dictionary<string, (Func<Transform, Transform>, ThreePart)>
        {
            ["carrierBow"] = (PartPort.CarrierBow, new ThreePart { Mesh = Primitives.Cone(36, 70, 4), Geometry = new[] { RotY(Math.PI / 4), RotZ(-Math.PI / 2) }, Position = new V(195, 10, 0) }),
            ["mantaDelta"] = (PartPort.MantaDelta, new ThreePart { Mesh = Primitives.Cone(13, 30, 3), Geometry = new[] { RotZ(-Math.PI / 2), Scale(1, 0.16, 1.7) }, Position = new V(-3, 0, 0) }),
            ["mantaNose"] = (PartPort.MantaNose, new ThreePart { Mesh = Primitives.Cone(2.2f, 8, 6), Geometry = new[] { RotZ(-Math.PI / 2) }, Position = new V(17, 2.2, 0) }),
            ["mantaFinPort"] = (m => PartPort.MantaFin(m, -1), new ThreePart { Mesh = Primitives.Box(7, 6, 0.8f), Rotation = new V(0.35, 0, 0), Position = new V(-9, 4.5, -5.5) }),
            ["mantaFinStarboard"] = (m => PartPort.MantaFin(m, 1), new ThreePart { Mesh = Primitives.Box(7, 6, 0.8f), Rotation = new V(-0.35, 0, 0), Position = new V(-9, 4.5, 5.5) }),
            ["lighterBow"] = (PartPort.LighterBow, new ThreePart { Mesh = Primitives.Cylinder(0.1f, 5.5f, 8, 4), Geometry = new[] { RotZ(-Math.PI / 2), RotX(Math.PI / 4) }, Position = new V(16.5, 3, 0) }),
            ["walrusWheel"] = (PartPort.WalrusWheel, new ThreePart { Mesh = Primitives.Cylinder(2.2f, 2.2f, 1.6f, 8), Geometry = new[] { RotX(Math.PI / 2) }, Position = new V(-5, 2.2, 5.1) }),
            ["turretRail"] = (PartPort.TurretRail, new ThreePart { Mesh = Primitives.Cylinder(2.6f, 2.6f, 34, 5), Geometry = new[] { RotZ(-Math.PI / 2.6) }, Position = new V(-4, 44, -12) }),
            ["crane"] = (PartPort.Crane, new ThreePart { Mesh = Primitives.Cylinder(1.6f, 2.2f, 42, 6), Geometry = new[] { RotZ(0.7) }, Position = new V(-150, 40, 14) }),
            ["dish"] = (PartPort.Dish, new ThreePart { Mesh = Primitives.Cylinder(7, 7, 2, 10), Rotation = new V(0.9, 0, 0), Position = new V(-30, 78, 26) }),
            ["canopy"] = (PartPort.Canopy, new ThreePart { Mesh = Primitives.Box(5.2f, 5.2f, 5.2f), Rotation = new V(0, 0.3, 0), MeshScale = new V(1.9, 0.9, 1), Position = new V(7, 4.2, 0) }),
        };

        // Every expected vertex has its own actual vertex (a primitive's vertex order around its axis
        // is not part of the contract, only where its corners end up).
        static void SameVertices(string part, V[] expected, Vector3[] actual)
        {
            Assert.Equal(expected.Length, actual.Length);
            var left = actual.ToList();
            foreach (V e in expected)
            {
                double tol = 1e-3 + 1e-5 * Math.Sqrt(e.X * e.X + e.Y * e.Y + e.Z * e.Z);
                int hit = left.FindIndex(a => Math.Abs(a.x - e.X) <= tol && Math.Abs(a.y - e.Y) <= tol && Math.Abs(a.z - e.Z) <= tol);
                Assert.True(hit >= 0, $"{part}: no vertex at ({e.X:F3}, {e.Y:F3}, {e.Z:F3}); got {string.Join(" ", left.Select(a => $"({a.x:F3}, {a.y:F3}, {a.z:F3})"))}");
                left.RemoveAt(hit);
            }
        }

        static void Check(string part, Transform model)
        {
            var (port, three) = Parts[part];
            Transform carrier = port(model);
            Assert.NotNull(carrier);
            Transform t = carrier;
            while (t != null && t != model) t = t.parent;
            Assert.True(t == model, $"{part}: the returned transform is not under the model");
            V[] expected = three.World().Select(v =>
            {
                Vector3 w = model.TransformPoint(new Vector3((float)v.X, (float)v.Y, (float)v.Z));
                return new V(w.x, w.y, w.z);
            }).ToArray();
            SameVertices(part, expected, three.Mesh.vertices.Select(carrier.TransformPoint).ToArray());
        }

        [Theory]
        [InlineData("carrierBow")]
        [InlineData("mantaDelta")]
        [InlineData("mantaNose")]
        [InlineData("mantaFinPort")]
        [InlineData("mantaFinStarboard")]
        [InlineData("lighterBow")]
        [InlineData("walrusWheel")]
        [InlineData("turretRail")]
        [InlineData("crane")]
        [InlineData("dish")]
        [InlineData("canopy")]
        public void Part_LandsWhereTheBrowserDrawsIt(string part) => Check(part, new GameObject("model").transform);

        [Fact]
        public void Parts_AreBuiltInModelSpace_NotWorldSpace()
        {
            var model = new GameObject("model").transform;
            model.localPosition = new Vector3(400, 12, -250);
            model.localRotation = Quaternion.Euler(0, 37, 0);
            model.localScale = new Vector3(2, 2, 2);
            foreach (string part in new[] { "carrierBow", "mantaDelta", "mantaFinStarboard", "canopy" }) Check(part, model);
        }

        [Fact]
        public void ShimTransform_ComposesScaleThenRotationThenPosition()
        {
            var root = new GameObject("r").transform;
            root.localPosition = new Vector3(1, 2, 3);
            root.localRotation = Quaternion.Euler(0, 90, 0);
            root.localScale = new Vector3(2, 1, 1);
            Assert.True(root.TransformPoint(new Vector3(1, 0, 0)) == new Vector3(1, 2, 1), root.TransformPoint(new Vector3(1, 0, 0)).ToString());
        }
    }
}
