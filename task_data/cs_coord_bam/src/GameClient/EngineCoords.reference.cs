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

        // Unity: x east, y up, z north (left-handed).
        public static Vector3 Position(int x, int y, int altitude)
        {
            return new Vector3(x / (float)UnitsPerMeter, altitude / (float)UnitsPerMeter, y / (float)UnitsPerMeter);
        }

        // Same rounding as the server's JavaScript Math.round: halves round toward +infinity.
        public static int ToUnits(float meters)
        {
            if (float.IsNaN(meters) || float.IsInfinity(meters)) throw new ArgumentException("not finite", nameof(meters));
            double units = Math.Floor((double)meters * UnitsPerMeter + 0.5);
            if (units < int.MinValue || units > int.MaxValue) throw new ArgumentOutOfRangeException(nameof(meters));
            return (int)units;
        }

        // Unity yaw is clockwise from +z (north) seen from above; BAM is counter-clockwise from east.
        public static float YawDegrees(int bam)
        {
            CheckBam(bam);
            double deg = 90.0 - bam * 360.0 / BamPerTurn;
            if (deg < 0) deg += 360.0;
            return (float)deg;
        }

        public static Quaternion Rotation(int bam)
        {
            return Quaternion.Euler(0f, YawDegrees(bam), 0f);
        }

        public static Vector3 Forward(int bam)
        {
            CheckBam(bam);
            double h = bam * 2.0 * Math.PI / BamPerTurn;
            return new Vector3((float)Math.Cos(h), 0f, (float)Math.Sin(h));
        }

        public static int HeadingFromYaw(float yawDegrees)
        {
            if (float.IsNaN(yawDegrees) || float.IsInfinity(yawDegrees)) throw new ArgumentException("not finite", nameof(yawDegrees));
            double bam = Math.Floor((90.0 - yawDegrees) / 360.0 * BamPerTurn + 0.5);
            long wrapped = (long)bam % BamPerTurn;
            return (int)(wrapped < 0 ? wrapped + BamPerTurn : wrapped);
        }

        static void CheckBam(int bam)
        {
            if (bam < 0 || bam >= BamPerTurn) throw new ArgumentOutOfRangeException(nameof(bam));
        }
    }
}
