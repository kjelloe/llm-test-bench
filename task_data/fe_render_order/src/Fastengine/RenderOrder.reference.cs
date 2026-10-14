using System;
using System.Collections.Generic;

namespace Fastengine
{
    public sealed class SceneNode
    {
        public int Id;
        public string Kind;
        public int RenderOrder;
        public bool Visible = true;
        public double[] World;
        public double[] Center;
        public double Radius = 1;
        public bool FrustumCulled = true;
        public int Layers = 1;
        public RenderMaterial Material;
        public List<RenderMaterial> Materials;
        public List<int> GroupMaterials;
        public List<SceneNode> Children = new();
    }

    public sealed class RenderMaterial
    {
        public int Id;
        public bool Transparent;
        public double Transmission;
        public bool Visible = true;
    }

    public sealed record RenderLists(List<int> Opaque, List<int> Transmissive, List<int> Transparent);

    public static class RenderOrder
    {
        sealed record Item(int Id, int MaterialId, int GroupOrder, int RenderOrder, double Z, int Seq);

        public static RenderLists Build(SceneNode scene, double[] viewProjection, double[] cameraPosition, int cameraLayers = 1)
        {
            var opaque = new List<Item>();
            var transmissive = new List<Item>();
            var transparent = new List<Item>();
            var planes = Frustum(viewProjection);
            Project(scene, viewProjection, planes, cameraLayers, 0, opaque, transmissive, transparent);
            opaque.Sort(PainterSortStable);
            transmissive.Sort(ReversePainterSortStable);
            transparent.Sort(ReversePainterSortStable);
            return new RenderLists(opaque.ConvertAll(i => i.Id), transmissive.ConvertAll(i => i.Id), transparent.ConvertAll(i => i.Id));
        }

        static void Project(SceneNode node, double[] proj, double[][] planes, int cameraLayers, int groupOrder,
            List<Item> opaque, List<Item> transmissive, List<Item> transparent)
        {
            if (!node.Visible) return;
            if ((node.Layers & cameraLayers) == 0) { } // not drawn, but its children are still visited
            else if (node.Kind == "group") groupOrder = node.RenderOrder;
            else if (node.Kind == "sprite" && node.FrustumCulled && !InFrustum(planes, node.World, 0, 0, 0, 0.7071067811865476)) { }
            else if (node.Kind is "mesh" or "line" or "points" && node.FrustumCulled
                     && !InFrustum(planes, node.World, node.Center[0], node.Center[1], node.Center[2], node.Radius)) { }
            else if (node.Kind == "sprite")
            {
                var (_, _, z) = Apply(proj, node.World[12], node.World[13], node.World[14]);
                if (node.Material.Visible) Push(node, node.Material, groupOrder, z, opaque, transmissive, transparent);
            }
            else if (node.Kind is "mesh" or "line" or "points")
            {
                var (x, y, z) = Apply(node.World, node.Center[0], node.Center[1], node.Center[2]);
                (_, _, z) = Apply(proj, x, y, z);
                if (node.Materials != null)
                {
                    foreach (var index in node.GroupMaterials)
                    {
                        var gm = index >= 0 && index < node.Materials.Count ? node.Materials[index] : null;
                        if (gm != null && gm.Visible) Push(node, gm, groupOrder, z, opaque, transmissive, transparent);
                    }
                }
                else if (node.Material.Visible) Push(node, node.Material, groupOrder, z, opaque, transmissive, transparent);
            }
            foreach (var child in node.Children) Project(child, proj, planes, cameraLayers, groupOrder, opaque, transmissive, transparent);
        }

        static void Push(SceneNode node, RenderMaterial m, int groupOrder, double z, List<Item> opaque, List<Item> transmissive, List<Item> transparent)
        {
            var item = new Item(node.Id, m.Id, groupOrder, node.RenderOrder, z, opaque.Count + transmissive.Count + transparent.Count);
            (m.Transmission > 0 ? transmissive : m.Transparent ? transparent : opaque).Add(item);
        }

        // Frustum.setFromProjectionMatrix (WebGL): six planes (a, b, c, d), normalised.
        static double[][] Frustum(double[] me)
        {
            double[][] raw =
            {
                new[] { me[3] - me[0], me[7] - me[4], me[11] - me[8], me[15] - me[12] },
                new[] { me[3] + me[0], me[7] + me[4], me[11] + me[8], me[15] + me[12] },
                new[] { me[3] + me[1], me[7] + me[5], me[11] + me[9], me[15] + me[13] },
                new[] { me[3] - me[1], me[7] - me[5], me[11] - me[9], me[15] - me[13] },
                new[] { me[3] - me[2], me[7] - me[6], me[11] - me[10], me[15] - me[14] },
                new[] { me[3] + me[2], me[7] + me[6], me[11] + me[10], me[15] + me[14] },
            };
            foreach (var p in raw)
            {
                var inv = 1 / Math.Sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]);
                for (int i = 0; i < 4; i++) p[i] *= inv;
            }
            return raw;
        }

        // Frustum.intersectsSphere of the local sphere moved by the world matrix (Sphere.applyMatrix4: the radius scales by
        // the largest axis scale).
        static bool InFrustum(double[][] planes, double[] w, double cx, double cy, double cz, double radius)
        {
            var (x, y, z) = Apply(w, cx, cy, cz);
            double sx = w[0] * w[0] + w[1] * w[1] + w[2] * w[2], sy = w[4] * w[4] + w[5] * w[5] + w[6] * w[6], sz = w[8] * w[8] + w[9] * w[9] + w[10] * w[10];
            var r = radius * Math.Sqrt(Math.Max(sx, Math.Max(sy, sz)));
            foreach (var p in planes)
                if (p[0] * x + p[1] * y + p[2] * z + p[3] < -r) return false;
            return true;
        }

        // three's Vector3.applyMatrix4: column-major, divided by w
        static (double, double, double) Apply(double[] e, double x, double y, double z)
        {
            double w = 1 / (e[3] * x + e[7] * y + e[11] * z + e[15]);
            return ((e[0] * x + e[4] * y + e[8] * z + e[12]) * w, (e[1] * x + e[5] * y + e[9] * z + e[13]) * w,
                (e[2] * x + e[6] * y + e[10] * z + e[14]) * w);
        }

        static int PainterSortStable(Item a, Item b) =>
            a.GroupOrder != b.GroupOrder ? a.GroupOrder.CompareTo(b.GroupOrder)
            : a.RenderOrder != b.RenderOrder ? a.RenderOrder.CompareTo(b.RenderOrder)
            : a.MaterialId != b.MaterialId ? a.MaterialId.CompareTo(b.MaterialId)
            : a.Z != b.Z ? a.Z.CompareTo(b.Z)
            : a.Id != b.Id ? a.Id.CompareTo(b.Id)
            : a.Seq.CompareTo(b.Seq); // JS sort is stable

        static int ReversePainterSortStable(Item a, Item b) =>
            a.GroupOrder != b.GroupOrder ? a.GroupOrder.CompareTo(b.GroupOrder)
            : a.RenderOrder != b.RenderOrder ? a.RenderOrder.CompareTo(b.RenderOrder)
            : a.Z != b.Z ? b.Z.CompareTo(a.Z)
            : a.Id != b.Id ? a.Id.CompareTo(b.Id)
            : a.Seq.CompareTo(b.Seq);
    }
}
