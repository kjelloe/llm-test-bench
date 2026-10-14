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

        public static RenderLists Build(SceneNode scene, double[] viewProjection, double[] cameraPosition)
        {
            var opaque = new List<Item>();
            var transmissive = new List<Item>();
            var transparent = new List<Item>();
            Project(scene, viewProjection, 0, opaque, transmissive, transparent);
            opaque.Sort(PainterSortStable);
            transmissive.Sort(ReversePainterSortStable);
            transparent.Sort(ReversePainterSortStable);
            return new RenderLists(opaque.ConvertAll(i => i.Id), transmissive.ConvertAll(i => i.Id), transparent.ConvertAll(i => i.Id));
        }

        static void Project(SceneNode node, double[] proj, int groupOrder, List<Item> opaque, List<Item> transmissive, List<Item> transparent)
        {
            if (!node.Visible) return;
            if (node.Kind == "group") groupOrder = node.RenderOrder;
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
            foreach (var child in node.Children) Project(child, proj, groupOrder, opaque, transmissive, transparent);
        }

        static void Push(SceneNode node, RenderMaterial m, int groupOrder, double z, List<Item> opaque, List<Item> transmissive, List<Item> transparent)
        {
            var item = new Item(node.Id, m.Id, groupOrder, node.RenderOrder, z, opaque.Count + transmissive.Count + transparent.Count);
            (m.Transmission > 0 ? transmissive : m.Transparent ? transparent : opaque).Add(item);
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
