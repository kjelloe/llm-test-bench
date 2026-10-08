using System;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    public class EngineCoordsTests
    {
        static void Near(float expected, float actual, float tol = 1e-4f) =>
            Assert.True(Math.Abs(expected - actual) < tol, $"expected {expected} got {actual}");

        static void NearVec(Vector3 expected, Vector3 actual, float tol = 1e-4f) =>
            Assert.True((expected - actual).magnitude < tol, $"expected {expected} got {actual}");

        [Fact]
        public void Position_MapsNorthToPositiveZ_AltitudeToY_KeepsFractions()
        {
            NearVec(new Vector3(2f, 1f, 3f), EngineCoords.Position(512, 768, 256));
            NearVec(new Vector3(1f / 256f, 0f, -1f / 256f), EngineCoords.Position(1, -1, 0));
            NearVec(new Vector3(-0.5f, 0.25f, 10.5f), EngineCoords.Position(-128, 2688, 64));
        }

        [Theory]
        [InlineData(2.5f / 256f, 3)]
        [InlineData(-2.5f / 256f, -2)]   // JavaScript Math.round: halves go toward +infinity
        [InlineData(-3.5f / 256f, -3)]
        [InlineData(3.5f / 256f, 4)]
        [InlineData(1.25f, 320)]
        [InlineData(-1.25f, -320)]
        [InlineData(0.001f, 0)]
        public void ToUnits_RoundsLikeTheServer(float meters, int expected)
        {
            Assert.Equal(expected, EngineCoords.ToUnits(meters));
        }

        [Fact]
        public void ToUnits_RejectsNonFinite()
        {
            Assert.ThrowsAny<ArgumentException>(() => EngineCoords.ToUnits(float.NaN));
            Assert.ThrowsAny<ArgumentException>(() => EngineCoords.ToUnits(float.PositiveInfinity));
        }

        [Fact]
        public void PositionRoundTripsThroughToUnits()
        {
            foreach (int v in new[] { 0, 1, -1, 255, 256, -257, 123456, -987654 })
            {
                Vector3 p = EngineCoords.Position(v, -v, v / 2);
                Assert.Equal(v, EngineCoords.ToUnits(p.x));
                Assert.Equal(-v, EngineCoords.ToUnits(p.z));
                Assert.Equal(v / 2, EngineCoords.ToUnits(p.y));
            }
        }

        [Theory]
        [InlineData(0, 90f)]       // east
        [InlineData(16384, 0f)]    // north
        [InlineData(32768, 270f)]  // west
        [InlineData(49152, 180f)]  // south
        [InlineData(8192, 45f)]    // north-east
        [InlineData(65535, 90.0054932f)]
        public void YawDegrees_IsClockwiseFromNorth(int bam, float expected)
        {
            float yaw = EngineCoords.YawDegrees(bam);
            Assert.InRange(yaw, 0f, 359.99999f);
            Near(expected, yaw, 1e-3f);
        }

        [Fact]
        public void YawDegrees_RejectsOutOfRangeBam()
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => EngineCoords.YawDegrees(65536));
            Assert.Throws<ArgumentOutOfRangeException>(() => EngineCoords.YawDegrees(-1));
            Assert.Throws<ArgumentOutOfRangeException>(() => EngineCoords.Forward(70000));
        }

        [Fact]
        public void Forward_PointsAlongTheHeading()
        {
            NearVec(new Vector3(1f, 0f, 0f), EngineCoords.Forward(0));
            NearVec(new Vector3(0f, 0f, 1f), EngineCoords.Forward(16384));
            NearVec(new Vector3(-1f, 0f, 0f), EngineCoords.Forward(32768));
            NearVec(new Vector3(0f, 0f, -1f), EngineCoords.Forward(49152));
        }

        [Fact]
        public void RotationTurnsUnityForwardOntoTheHeading()
        {
            for (int bam = 0; bam < 65536; bam += 4099)
                NearVec(EngineCoords.Forward(bam), EngineCoords.Rotation(bam) * Vector3.forward, 1e-3f);
        }

        [Fact]
        public void MovingAlongForwardMatchesEngineMovement()
        {
            // The engine moves a unit 256 units along its heading per tick; Unity must agree.
            int bam = 10923; // about 60 degrees north of east
            double h = bam * 2.0 * Math.PI / 65536;
            int dx = (int)Math.Round(256 * Math.Cos(h)), dy = (int)Math.Round(256 * Math.Sin(h));
            Vector3 start = EngineCoords.Position(1000, 2000, 0);
            Vector3 end = EngineCoords.Position(1000 + dx, 2000 + dy, 0);
            NearVec(end - start, EngineCoords.Rotation(bam) * Vector3.forward, 0.01f);
        }

        [Theory]
        [InlineData(90f, 0)]
        [InlineData(0f, 16384)]
        [InlineData(270f, 32768)]
        [InlineData(180f, 49152)]
        [InlineData(450f, 0)]
        [InlineData(-90f, 32768)]
        [InlineData(89.99725341796875f, 1)]  // exactly half a BAM: rounds up like Math.round
        [InlineData(90.00274658203125f, 0)]  // exactly minus half: rounds up to 0, never 65535
        public void HeadingFromYaw_IsTheInverse(float yaw, int expected)
        {
            Assert.Equal(expected, EngineCoords.HeadingFromYaw(yaw));
        }

        [Fact]
        public void HeadingRoundTripsThroughYaw()
        {
            for (int bam = 0; bam < 65536; bam += 997)
                Assert.Equal(bam, EngineCoords.HeadingFromYaw(EngineCoords.YawDegrees(bam)));
        }
    }
}
