using System;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    public class CoordConvertTests
    {
        const float Tol = 1e-4f;

        static void AssertVec(Vector3 expected, Vector3 actual)
        {
            Assert.True(Math.Abs(expected.x - actual.x) < Tol &&
                        Math.Abs(expected.y - actual.y) < Tol &&
                        Math.Abs(expected.z - actual.z) < Tol,
                $"expected {expected} got {actual}");
        }

        static void AssertSameRotation(Quaternion expected, Quaternion actual)
        {
            Assert.True(Quaternion.Angle(expected, actual) < 0.05f,
                $"expected {expected} got {actual} (angle {Quaternion.Angle(expected, actual)} deg)");
        }

        static float CircularDiff(float a, float b)
        {
            float d = Math.Abs(a - b) % 360f;
            return d > 180f ? 360f - d : d;
        }

        [Fact]
        public void Position_MirrorsZ_AndConvertsToMeters()
        {
            AssertVec(new Vector3(1f, 2.5f, -3f), ThreeToUnity.Position(new double[] { 100, 250, 300 }));
            AssertVec(new Vector3(-0.5f, 0f, 0.25f), ThreeToUnity.Position(new double[] { -50, 0, -25 }));
        }

        [Fact]
        public void Velocity_MirrorsZ_AndConvertsToMetersPerSecond()
        {
            AssertVec(new Vector3(4f, -9.81f, -2f), ThreeToUnity.Velocity(new double[] { 400, -981, 200 }));
        }

        [Fact]
        public void Rotation_PureYaw_MatchesYawDegrees()
        {
            double theta = 0.7;
            var q = new double[] { 0, Math.Sin(theta / 2), 0, Math.Cos(theta / 2) };
            AssertSameRotation(Quaternion.Euler(0f, ThreeToUnity.YawDegrees(theta), 0f), ThreeToUnity.Rotation(q));
            AssertSameRotation(Quaternion.Euler(0f, -40.107f, 0f), ThreeToUnity.Rotation(q));
        }

        [Fact]
        public void Rotation_RotatedVectorsAgreeAcrossConventions()
        {
            // Rotate a point in Three.js space, then convert; must equal converting first,
            // then rotating with the converted quaternion in Unity space.
            var axis = new Vector3(1f, 2f, 3f).normalized;
            double angle = 1.1;
            double s = Math.Sin(angle / 2);
            var qThree = new double[] { axis.x * s, axis.y * s, axis.z * s, Math.Cos(angle / 2) };
            var rawQ = new Quaternion((float)qThree[0], (float)qThree[1], (float)qThree[2], (float)qThree[3]);
            var vThree = new double[] { 10, -20, 5 };   // not parallel to the axis, or any rotation passes
            Vector3 rotatedThree = rawQ * new Vector3(10f, -20f, 5f);

            Vector3 viaThree = ThreeToUnity.Position(new double[] { rotatedThree.x, rotatedThree.y, rotatedThree.z });
            Vector3 viaUnity = ThreeToUnity.Rotation(qThree) * ThreeToUnity.Position(vThree);
            AssertVec(viaThree, viaUnity);
        }

        [Fact]
        public void Rotation_IsNormalized()
        {
            Quaternion q = ThreeToUnity.Rotation(new double[] { 0, 0, 0, 2 });
            AssertSameRotation(Quaternion.identity, q);
            Quaternion r = ThreeToUnity.Rotation(new double[] { 0.2, 0.4, 0.1, 0.9 });
            float norm = (float)Math.Sqrt(Quaternion.Dot(r, r));
            Assert.InRange(norm, 0.9999f, 1.0001f);
        }

        [Theory]
        [InlineData(0.0, 0f)]
        [InlineData(Math.PI / 2, 270f)]
        [InlineData(-Math.PI / 2, 90f)]
        [InlineData(7 * Math.PI / 2, 90f)]
        [InlineData(2 * Math.PI, 0f)]
        [InlineData(-5.0, 286.4789f)]
        public void YawDegrees_NegatesAndWrapsIntoRange(double radians, float expected)
        {
            float yaw = ThreeToUnity.YawDegrees(radians);
            Assert.InRange(yaw, 0f, 359.99999f);
            Assert.True(CircularDiff(expected, yaw) < 0.01f, $"expected {expected} got {yaw}");
        }

        [Fact]
        public void PositionToServer_IsInverseOfPosition()
        {
            double[] server = ThreeToUnity.PositionToServer(new Vector3(1f, 2.5f, -3f));
            Assert.Equal(3, server.Length);
            Assert.Equal(100.0, server[0], 3);
            Assert.Equal(250.0, server[1], 3);
            Assert.Equal(300.0, server[2], 3);

            var original = new double[] { -1234.5, 87.25, 4096 };
            double[] roundTrip = ThreeToUnity.PositionToServer(ThreeToUnity.Position(original));
            for (int i = 0; i < 3; i++)
                Assert.True(Math.Abs(original[i] - roundTrip[i]) < 0.01, $"component {i}: {original[i]} vs {roundTrip[i]}");
        }

        [Fact]
        public void RejectsMalformedInput()
        {
            Assert.ThrowsAny<ArgumentException>(() => ThreeToUnity.Position(null));
            Assert.ThrowsAny<ArgumentException>(() => ThreeToUnity.Position(new double[] { 1, 2 }));
            Assert.ThrowsAny<ArgumentException>(() => ThreeToUnity.Velocity(new double[] { 1, double.NaN, 3 }));
            Assert.ThrowsAny<ArgumentException>(() => ThreeToUnity.Rotation(new double[] { 0, 0, 0 }));
            Assert.ThrowsAny<ArgumentException>(() => ThreeToUnity.Rotation(new double[] { 0, 0, double.PositiveInfinity, 1 }));
            Assert.ThrowsAny<ArgumentException>(() => ThreeToUnity.YawDegrees(double.NaN));
        }
    }
}
