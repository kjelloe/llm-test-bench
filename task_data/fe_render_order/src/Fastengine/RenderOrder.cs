using System;
using System.Collections.Generic;
using System.Linq;

namespace Fastengine
{
    // One node of the scene graph as the renderer sees it each frame. Kind is "group" (three's Group), "object" (a plain
    // Object3D), "light", "mesh", "line", "points" or "sprite". World is the node's world matrix and ViewProjection the camera's
    // projectionMatrix × matrixWorldInverse, both as three stores matrices: 16 numbers, column-major.
    // Center is the centre of the geometry's bounding sphere, in the node's local space (none for a sprite).
    public sealed class SceneNode
    {
        public int Id;
        public string Kind;
        public int RenderOrder;
        public bool Visible = true;
        public double[] World;
        public double[] Center;
        public RenderMaterial Material;
        // A mesh, line or points with several materials (three's material array): Materials, and the material index of
        // each geometry group in group order (an index may point past the array). Material is then null.
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

    // fastengine spec B06: draw in the order three r162's WebGLRenderer does (js/three-r162-renderlist.js), so
    // transparent surfaces blend in the same order as in the browser. Build returns the object id of each item of each
    // list in draw order (an object with several materials can appear more than once). Frustum culling, layers and
    // LOD are not ported: every visible object is drawn.
    public static class RenderOrder
    {
        public static RenderLists Build(SceneNode scene, double[] viewProjection, double[] cameraPosition)
        {
            var opaque = new List<(SceneNode node, int index)>();
            var transparent = new List<(SceneNode node, int index, double distance)>();
            Collect(scene, cameraPosition, opaque, transparent);
            // opaque by renderOrder, transparent by renderOrder then far to near; the index keeps it stable
            var o = opaque.OrderBy(x => x.node.RenderOrder).ThenBy(x => x.index).Select(x => x.node.Id).ToList();
            var t = transparent.OrderBy(x => x.node.RenderOrder).ThenByDescending(x => x.distance).ThenBy(x => x.index)
                .Select(x => x.node.Id).ToList();
            return new RenderLists(o, new List<int>(), t);
        }

        static void Collect(SceneNode node, double[] camera, List<(SceneNode, int)> opaque,
            List<(SceneNode, int, double)> transparent)
        {
            if (!node.Visible) return;
            if (node.Kind == "mesh")
            {
                if (node.Material.Transparent)
                {
                    double dx = node.World[12] - camera[0], dy = node.World[13] - camera[1], dz = node.World[14] - camera[2];
                    transparent.Add((node, transparent.Count, dx * dx + dy * dy + dz * dz));
                }
                else opaque.Add((node, opaque.Count));
            }
            foreach (var child in node.Children) Collect(child, camera, opaque, transparent);
        }
    }
}
