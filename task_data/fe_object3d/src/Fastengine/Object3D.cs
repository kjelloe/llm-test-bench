using System;
using System.Collections.Generic;
using System.Numerics;

namespace Fastengine.Three
{
    // three.js Object3D (fastengine spec B02): position, Euler XYZ rotation in radians, scale, children.
    // Matrices are System.Numerics (row vectors): local = S · Rz · Ry · Rx · T, which is three's T · Rx · Ry · Rz · S,
    // so M11..M44 read in order are three's matrix.elements (column-major) and M41..M43 is the translation.
    // three's own code is in js/three-r162-object3d.js.
    public class Object3D
    {
        public Vector3 Position;
        public Vector3 Rotation;
        public Vector3 Scale = Vector3.One;
        public Object3D Parent { get; private set; }
        public readonly List<Object3D> Children = new();

        public T Add<T>(T child) where T : Object3D
        {
            child.Parent?.Children.Remove(child);
            child.Parent = this;
            Children.Add(child);
            return child;
        }

        public Matrix4x4 LocalMatrix =>
            Matrix4x4.CreateScale(Scale)
            * Matrix4x4.CreateRotationZ(Rotation.Z) * Matrix4x4.CreateRotationY(Rotation.Y) * Matrix4x4.CreateRotationX(Rotation.X)
            * Matrix4x4.CreateTranslation(Position);

        // three's matrixWorld: the parent's world matrix times this local matrix.
        public Matrix4x4 WorldMatrix => LocalMatrix;

        // three's Object3D.lookAt(target), target in world space: turn this object so that its +Z axis (a Camera's -Z
        // axis) points at the target, keeping Rotation an Euler XYZ as three keeps object.rotation in step with
        // object.quaternion. Parents with non-uniform scale need not be supported, as in three.
        public virtual void LookAt(Vector3 target) => throw new NotImplementedException();
    }

    public class Camera : Object3D { }
}
