using System;
using UnityEngine;

namespace GameClient
{
    /// <summary>
    /// The one place the Node engine's integer world becomes Unity floats.
    /// Ported from the Three.js client's coords.js.
    ///
    /// Engine: x east, y north, z up (altitude); 256 units per meter; integers.
    /// Headings are BAM: 0..65535 is one full turn, 0 = east, counter-clockwise toward north.
    /// </summary>
    public static class EngineCoords
    {
        public const int UnitsPerMeter = 256;
        public const int BamPerTurn = 65536;

        public static Vector3 Position(int x, int y, int altitude)
        {
            return new Vector3(x / UnitsPerMeter, altitude / UnitsPerMeter, -y / UnitsPerMeter);
        }

        public static int ToUnits(float meters)
        {
            return (int)Math.Round(meters * UnitsPerMeter);
        }

        public static float YawDegrees(int bam)
        {
            return bam / (float)BamPerTurn * 360f;
        }

        public static Quaternion Rotation(int bam)
        {
            return Quaternion.Euler(0f, YawDegrees(bam), 0f);
        }

        public static Vector3 Forward(int bam)
        {
            float yaw = bam / (float)BamPerTurn * Mathf.PI * 2f;
            return new Vector3(Mathf.Cos(yaw), 0f, -Mathf.Sin(yaw));
        }

        public static int HeadingFromYaw(float yawDegrees)
        {
            float turns = yawDegrees / 360f;
            return (int)Math.Round(turns * BamPerTurn) % BamPerTurn;
        }
    }
}
