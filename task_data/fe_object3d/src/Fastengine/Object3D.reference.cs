using System;
using System.Collections.Generic;
using System.Numerics;

namespace Fastengine.Three
{
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

        public Matrix4x4 WorldMatrix => Parent == null ? LocalMatrix : LocalMatrix * Parent.WorldMatrix;

        public void LookAt(Vector3 target)
        {
            var w = WorldMatrix;
            var position = new Vector3(w.M41, w.M42, w.M43);
            var rotation = this is Camera ? LookRotation(position, target) : LookRotation(target, position);
            if (Parent != null) rotation *= Matrix4x4.Transpose(RotationOnly(Parent.WorldMatrix));
            Rotation = EulerXyz(rotation);
        }

        // three's Matrix4.lookAt(eye, target, up = (0,1,0)) as a row-vector rotation: rows are x, y, z axes.
        static Matrix4x4 LookRotation(Vector3 eye, Vector3 target)
        {
            var up = Vector3.UnitY;
            var z = eye - target;
            if (z.LengthSquared() == 0) z.Z = 1;
            z = Vector3.Normalize(z);
            var x = Vector3.Cross(up, z);
            if (x.LengthSquared() == 0)
            {
                z.Z += 0.0001f;
                z = Vector3.Normalize(z);
                x = Vector3.Cross(up, z);
            }
            x = Vector3.Normalize(x);
            var y = Vector3.Cross(z, x);
            return new Matrix4x4(x.X, x.Y, x.Z, 0, y.X, y.Y, y.Z, 0, z.X, z.Y, z.Z, 0, 0, 0, 0, 1);
        }

        static Matrix4x4 RotationOnly(Matrix4x4 m)
        {
            var r0 = Vector3.Normalize(new Vector3(m.M11, m.M12, m.M13));
            var r1 = Vector3.Normalize(new Vector3(m.M21, m.M22, m.M23));
            var r2 = Vector3.Normalize(new Vector3(m.M31, m.M32, m.M33));
            return new Matrix4x4(r0.X, r0.Y, r0.Z, 0, r1.X, r1.Y, r1.Z, 0, r2.X, r2.Y, r2.Z, 0, 0, 0, 0, 1);
        }

        // three's Euler.setFromRotationMatrix, order XYZ; three's m11..m33 (column-vector) are the transpose here.
        static Vector3 EulerXyz(Matrix4x4 r)
        {
            float m11 = r.M11, m12 = r.M21, m13 = r.M31, m22 = r.M22, m23 = r.M32, m32 = r.M23, m33 = r.M33;
            float y = MathF.Asin(Math.Clamp(m13, -1, 1));
            return MathF.Abs(m13) < 0.9999999f
                ? new Vector3(MathF.Atan2(-m23, m33), y, MathF.Atan2(-m12, m11))
                : new Vector3(MathF.Atan2(m32, m22), y, 0);
        }
    }

    public class Camera : Object3D { }
}
