using System;
using UnityEngine;

namespace GameClient
{
    /// <summary>
    /// Converts state received from the Node.js game server (Three.js conventions:
    /// right-handed, Y-up, centimeters, radians) into Unity conventions
    /// (left-handed, Y-up, meters, degrees), and back for outgoing positions.
    /// </summary>
    public static class ThreeToUnity
    {
        public const float CentimetersToMeters = 0.01f;

        public static Vector3 Position(double[] cm)
        {
            Validate(cm, 3);
            return new Vector3((float)cm[0], (float)cm[1], -(float)cm[2]) * CentimetersToMeters;
        }

        public static Vector3 Velocity(double[] cmPerSecond)
        {
            Validate(cmPerSecond, 3);
            return new Vector3((float)cmPerSecond[0], (float)cmPerSecond[1], -(float)cmPerSecond[2]) * CentimetersToMeters;
        }

        public static Quaternion Rotation(double[] q)
        {
            Validate(q, 4);
            return new Quaternion(-(float)q[0], -(float)q[1], (float)q[2], (float)q[3]).normalized;
        }

        public static float YawDegrees(double radians)
        {
            if (double.IsNaN(radians) || double.IsInfinity(radians))
                throw new ArgumentException("yaw must be finite", nameof(radians));
            double deg = -radians * (180.0 / Math.PI) % 360.0;
            if (deg < 0) deg += 360.0;
            float result = (float)deg;
            return result >= 360f ? 0f : result;
        }

        public static double[] PositionToServer(Vector3 meters)
        {
            return new double[] { meters.x * 100.0, meters.y * 100.0, -meters.z * 100.0 };
        }

        static void Validate(double[] values, int length)
        {
            if (values == null) throw new ArgumentNullException(nameof(values));
            if (values.Length != length)
                throw new ArgumentException($"expected {length} components, got {values.Length}", nameof(values));
            foreach (double v in values)
                if (double.IsNaN(v) || double.IsInfinity(v))
                    throw new ArgumentException("components must be finite", nameof(values));
        }
    }
}
