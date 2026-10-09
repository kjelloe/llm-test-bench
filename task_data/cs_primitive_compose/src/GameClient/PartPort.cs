using System;
using UnityEngine;

namespace GameClient
{
    // Ports of the parts in js/parts.js. Each method builds its part under `model` (the model's
    // root transform) and returns the transform that carries the part's mesh, which is the
    // Primitives mesh named in the comment, unchanged. Add holder GameObjects in between if needed.
    // Unity's z axis is the mirror of three's: a three.js model-space point (x, y, z) is (x, y, -z)
    // in Unity model space.
    public static class PartPort
    {
        public static Transform CarrierBow(Transform model) => throw new NotImplementedException();   // Primitives.Cone(36, 70, 4)
        public static Transform MantaDelta(Transform model) => throw new NotImplementedException();   // Primitives.Cone(13, 30, 3)
        public static Transform MantaNose(Transform model) => throw new NotImplementedException();    // Primitives.Cone(2.2f, 8, 6)
        public static Transform MantaFin(Transform model, int side) => throw new NotImplementedException(); // Primitives.Box(7, 6, 0.8f)
        public static Transform LighterBow(Transform model) => throw new NotImplementedException();   // Primitives.Cylinder(0.1f, 5.5f, 8, 4)
        public static Transform WalrusWheel(Transform model) => throw new NotImplementedException();  // Primitives.Cylinder(2.2f, 2.2f, 1.6f, 8)
        public static Transform TurretRail(Transform model) => throw new NotImplementedException();   // Primitives.Cylinder(2.6f, 2.6f, 34, 5)
        public static Transform Crane(Transform model) => throw new NotImplementedException();        // Primitives.Cylinder(1.6f, 2.2f, 42, 6)
        public static Transform Dish(Transform model) => throw new NotImplementedException();         // Primitives.Cylinder(7, 7, 2, 10)
        public static Transform Canopy(Transform model) => throw new NotImplementedException();       // Primitives.Box(5.2f, 5.2f, 5.2f)
    }
}
