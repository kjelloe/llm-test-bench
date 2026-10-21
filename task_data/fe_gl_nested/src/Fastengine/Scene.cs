using System;
using System.Collections.Generic;
using System.Numerics;
using Raylib_cs;

namespace Fastengine
{
    // A cut-down three.js scene graph: a flat list of meshes, each a raylib Mesh with its world matrix (System.Numerics
    // layout) and either a flat colour or a texture (Map, e.g. a render target's). Not editable.
    public sealed class Obj
    {
        public Mesh Mesh;
        public Matrix4x4 World = Matrix4x4.Identity;
        public Vector3 Color = Vector3.One;
        public Texture2D? Map;
        // three's Object3D.onBeforeRender, as fastengine runs it: (renderer, scene, camera), once per frame.
        public Action<Renderer, Scene, Camera> OnBeforeRender;
    }

    public sealed class Scene
    {
        public readonly List<Obj> Objects = new();
        public Color Background = Color.Black;
    }

    // three's PerspectiveCamera. Projection, when set, overrides the projection the camera's fov would give (three:
    // camera.projectionMatrix set by hand, as a Reflector does for its virtual camera), in System.Numerics layout and
    // GL clip space.
    public sealed class Camera
    {
        public Vector3 Position, Target, Up = Vector3.UnitY;
        public float Fov = 50, Near = 0.1f, Far = 100;
        public Matrix4x4? Projection;
    }
}
