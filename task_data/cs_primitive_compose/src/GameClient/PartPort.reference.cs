using UnityEngine;

namespace GameClient
{
    public static class PartPort
    {
        const float Deg = Mathf.Rad2Deg;
        static readonly Quaternion AlongX = Quaternion.Euler(0, 0, -90); // rotateZ(-PI/2)

        public static Transform CarrierBow(Transform model) =>
            Part(model, new Vector3(195, 10, 0), geometry: AlongX * Quaternion.Euler(0, -45, 0));

        public static Transform MantaDelta(Transform model) =>
            Part(model, new Vector3(-3, 0, 0), geometry: AlongX, geometryScale: new Vector3(1, 0.16f, 1.7f));

        public static Transform MantaNose(Transform model) => Part(model, new Vector3(17, 2.2f, 0), geometry: AlongX);

        public static Transform MantaFin(Transform model, int side) =>
            Part(model, new Vector3(-9, 4.5f, side * 5.5f), rotation: Quaternion.Euler(side * 0.35f * Deg, 0, 0));

        public static Transform LighterBow(Transform model) =>
            Part(model, new Vector3(16.5f, 3, 0), geometry: Quaternion.Euler(-45, 0, 0) * AlongX);

        public static Transform WalrusWheel(Transform model) =>
            Part(model, new Vector3(-5, 2.2f, 5.1f), geometry: Quaternion.Euler(-90, 0, 0));

        public static Transform TurretRail(Transform model) =>
            Part(model, new Vector3(-4, 44, -12), geometry: Quaternion.Euler(0, 0, -180f / 2.6f));

        public static Transform Crane(Transform model) =>
            Part(model, new Vector3(-150, 40, 14), geometry: Quaternion.Euler(0, 0, 0.7f * Deg));

        public static Transform Dish(Transform model) =>
            Part(model, new Vector3(-30, 78, 26), rotation: Quaternion.Euler(-0.9f * Deg, 0, 0));

        public static Transform Canopy(Transform model) =>
            Part(model, new Vector3(7, 4.2f, 0), rotation: Quaternion.Euler(0, -0.3f * Deg, 0), scale: new Vector3(1.9f, 0.9f, 1));

        // Mesh transform (position, rotation, scale) on a holder; the geometry's own scale on a child,
        // because it applies after the geometry rotation; the geometry rotation innermost. Mirroring z
        // negates rotations about x and y, and mirrors the primitive itself, which for these regular
        // prisms and boxes is the same vertex set turned 180 degrees about its axis.
        static Transform Part(Transform model, Vector3 position, Quaternion? rotation = null, Vector3? scale = null,
            Quaternion? geometry = null, Vector3? geometryScale = null)
        {
            var holder = new GameObject("part").transform;
            holder.SetParent(model, false);
            holder.localPosition = new Vector3(position.x, position.y, -position.z);
            holder.localRotation = rotation ?? Quaternion.identity;
            holder.localScale = scale ?? Vector3.one;
            var scaled = new GameObject("geometry-scale").transform;
            scaled.SetParent(holder, false);
            scaled.localScale = geometryScale ?? Vector3.one;
            var mesh = new GameObject("mesh").transform;
            mesh.SetParent(scaled, false);
            mesh.localRotation = (geometry ?? Quaternion.identity) * Quaternion.Euler(0, 180, 0);
            return mesh;
        }
    }
}
