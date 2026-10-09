using System;
using UnityEngine;

namespace GameClient
{
    // Procedural primitives for the Unity client, flat-shaded like the browser clients'
    // flatShading Lambert meshes, so views need neither built-in resources nor the physics
    // module that GameObject.CreatePrimitive drags in.
    public static class Meshes
    {
        // Unit cube centred on the origin.
        public static Mesh Box() => throw new NotImplementedException();

        // UV sphere of diameter 1 centred on the origin: `segments` around the Y axis, `rings`
        // from pole to pole.
        public static Mesh Sphere(int segments, int rings) => throw new NotImplementedException();

        // Regular icosahedron of radius 1 (three.js IcosahedronGeometry(1, 0)).
        public static Mesh Icosahedron() => throw new NotImplementedException();

        // Flat-sided cylinder along +Y, centred, capped (three.js CylinderGeometry); radiusTop 0
        // makes a cone.
        public static Mesh Cylinder(float radiusTop, float radiusBottom, float height, int segments) => throw new NotImplementedException();

        // Ring around the Y axis in the XZ plane: `radius` to the tube's centre, tube radius `tube`.
        public static Mesh Torus(float radius, float tube, int radialSegments, int tubularSegments) => throw new NotImplementedException();
    }
}
