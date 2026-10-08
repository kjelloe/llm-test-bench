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
            return new Vector3((float)cm[0], (float)cm[1], (float)cm[2]) * CentimetersToMeters;
        }

        public static Vector3 Velocity(double[] cmPerSecond)
        {
            return new Vector3((float)cmPerSecond[0], (float)cmPerSecond[1], -(float)cmPerSecond[2]);
        }

        public static Quaternion Rotation(double[] q)
        {
            return new Quaternion((float)q[0], (float)q[1], -(float)q[2], (float)q[3]);
        }

        public static float YawDegrees(double radians)
        {
            return (float)(radians * Mathf.Rad2Deg) % 360f;
        }

        public static double[] PositionToServer(Vector3 meters)
        {
            return new double[] { meters.x / 100.0, meters.y / 100.0, -meters.z / 100.0 };
        }
    }
}
