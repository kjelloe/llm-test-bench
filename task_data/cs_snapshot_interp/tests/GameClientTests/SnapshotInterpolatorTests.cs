using System;
using System.Collections.Generic;
using System.Linq;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    public class SnapshotInterpolatorTests
    {
        static EntityState E(int id, int x, int y = 0, byte heading = 0, bool teleported = false) =>
            new EntityState { Id = id, X = x, Y = y, Heading = heading, Teleported = teleported };

        static Snapshot S(int tick, params EntityState[] entities) =>
            new Snapshot { Tick = tick, Entities = entities.ToList() };

        static RenderEntity Find(List<RenderEntity> list, int id) => list.Single(r => r.Id == id);

        static void Near(float expected, float actual, float tol = 1e-3f) =>
            Assert.True(Math.Abs(expected - actual) < tol, $"expected {expected} got {actual}");

        static void SameRotation(Quaternion expected, Quaternion actual) =>
            Assert.True(Quaternion.Angle(expected, actual) < 0.1f, $"expected {expected} got {actual}");

        [Fact]
        public void Constructor_RejectsInvalidArguments()
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => new SnapshotInterpolator(-1));
            Assert.Throws<ArgumentOutOfRangeException>(() => new SnapshotInterpolator(100, 1));
            Assert.Throws<ArgumentOutOfRangeException>(() => new SnapshotInterpolator(100, 32, -5));
            Assert.Throws<ArgumentNullException>(() => new SnapshotInterpolator().Push(null, 0));
        }

        [Fact]
        public void Sample_WithNoSnapshots_IsNull()
        {
            Assert.Null(new SnapshotInterpolator().Sample(5000));
        }

        [Fact]
        public void Sample_InterpolatesDelayBehind_AndConvertsToMeters()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0, 512)), 1000);
            interp.Push(S(2, E(1, 256, 768)), 1050);

            RenderEntity r = Find(interp.Sample(1125), 1); // render time 1025, halfway
            Near(0.5f, r.Position.x);
            Near(0f, r.Position.y);
            Near(2.5f, r.Position.z);
        }

        [Fact]
        public void Sample_BeforeOldest_UsesOldestFollowingSnapshot()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 256)), 1000);
            interp.Push(S(2, E(1, 512)), 1050);
            RenderEntity r = Find(interp.Sample(1000), 1); // render time 900
            Near(1f, r.Position.x);
            Assert.Null(r.MotionHeading);
        }

        [Fact]
        public void Push_DropsOutOfOrderAndStaleTicks()
        {
            var interp = new SnapshotInterpolator(delayMs: 0);
            interp.Push(S(5, E(1, 256)), 1000);
            interp.Push(S(4, E(1, 9999)), 1010);   // older tick, later arrival
            interp.Push(S(5, E(1, 7777)), 1020);   // duplicate tick
            interp.Push(S(6, E(1, 8888)), 990);    // arrives with an earlier timestamp
            Assert.Equal(1, interp.Count);
            Near(1f, Find(interp.Sample(1000), 1).Position.x);
        }

        [Fact]
        public void Push_EvictsOldestBeyondCapacity()
        {
            var interp = new SnapshotInterpolator(delayMs: 0, capacity: 4);
            for (int i = 0; i < 10; i++) interp.Push(S(i, E(1, i * 256)), 1000 + i * 50);
            Assert.Equal(4, interp.Count);
            // render time far before the buffer: the oldest retained snapshot is tick 6
            Near(6f, Find(interp.Sample(0), 1).Position.x);
        }

        [Fact]
        public void NewEntity_AppearsAtItsPosition_WithoutMotion()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0)), 1000);
            interp.Push(S(2, E(1, 256), E(2, 1024, 256)), 1050);
            RenderEntity r = Find(interp.Sample(1125), 2);
            Near(4f, r.Position.x);
            Near(1f, r.Position.z);
            Assert.Null(r.MotionHeading);
        }

        [Fact]
        public void EntityMissingFromNewestSnapshot_IsNeverRendered()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0), E(2, 0)), 1000);
            interp.Push(S(2, E(1, 256), E(2, 256)), 1050);
            interp.Push(S(3, E(1, 512)), 1100); // entity 2 removed by the server
            List<RenderEntity> frame = interp.Sample(1125); // brackets ticks 1 and 2
            Assert.Single(frame);
            Assert.Equal(1, frame[0].Id);
        }

        [Fact]
        public void TeleportFlag_SnapsInsteadOfInterpolating()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0)), 1000);
            interp.Push(S(2, E(1, 256, 0, 0, teleported: true)), 1050);
            RenderEntity r = Find(interp.Sample(1125), 1);
            Near(1f, r.Position.x);
            Assert.Null(r.MotionHeading);
        }

        [Fact]
        public void LargeJump_SnapsInsteadOfInterpolating()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0), E(2, 0)), 1000);
            interp.Push(S(2, E(1, 513), E(2, 512)), 1050);  // 513 > TeleportDistanceUnits, 512 is not
            List<RenderEntity> frame = interp.Sample(1125);
            Near(513f / 256f, Find(frame, 1).Position.x);
            Near(1f, Find(frame, 2).Position.x);
        }

        [Fact]
        public void Heading_InterpolatesAlongShortestArc()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0, 0, 250), E(2, 0, 0, 10), E(3, 0, 0, 0)), 1000);
            interp.Push(S(2, E(1, 0, 0, 6), E(2, 0, 0, 20), E(3, 0, 0, 128)), 1050);
            List<RenderEntity> frame = interp.Sample(1125);
            SameRotation(Quaternion.Euler(0f, 0f, 0f), Find(frame, 1).Rotation);           // 250 -> 6 wraps through 0
            SameRotation(Quaternion.Euler(0f, 15f * 360f / 256f, 0f), Find(frame, 2).Rotation);
            Quaternion half = Find(frame, 3).Rotation;                                         // exactly opposite: 90 or 270 both ok
            Assert.True(Quaternion.Angle(Quaternion.Euler(0f, 90f, 0f), half) < 0.1f ||
                        Quaternion.Angle(Quaternion.Euler(0f, 270f, 0f), half) < 0.1f, half.ToString());
        }

        [Fact]
        public void Rotation_IsHeadingNotMotionDirection()
        {
            // The entity strafes along +Y while facing +X (heading 0); facing must not follow motion.
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0, 0, 0)), 1000);
            interp.Push(S(2, E(1, 0, 256, 0)), 1050);
            RenderEntity r = Find(interp.Sample(1125), 1);
            SameRotation(Quaternion.identity, r.Rotation);
            Assert.NotNull(r.MotionHeading);
            Near(Mathf.PI / 2f, r.MotionHeading.Value);
        }

        [Fact]
        public void MotionHeading_IsRadiansOfTravel_NullWhenStill()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 0), E(2, 256, 256), E(3, 512)), 1000);
            interp.Push(S(2, E(1, 256), E(2, 0, 0), E(3, 512)), 1050);
            List<RenderEntity> frame = interp.Sample(1125);
            Near(0f, Find(frame, 1).MotionHeading.Value);
            Near(Mathf.Atan2(-256f, -256f), Find(frame, 2).MotionHeading.Value);
            Assert.Null(Find(frame, 3).MotionHeading);
        }

        [Fact]
        public void PastNewest_ExtrapolatesUpToTheCap()
        {
            var interp = new SnapshotInterpolator(delayMs: 100, capacity: 8, maxExtrapolationMs: 100);
            interp.Push(S(1, E(1, 0), E(2, 0)), 1000);
            interp.Push(S(2, E(1, 256), E(2, 256, 0, 0, teleported: true), E(3, 1024)), 1050);

            List<RenderEntity> a = interp.Sample(1200); // render time 1100: 50 ms past newest
            Near(2f, Find(a, 1).Position.x);
            Near(1f, Find(a, 2).Position.x);  // teleported: hold
            Near(4f, Find(a, 3).Position.x);  // no previous sample: hold
            Near(0f, Find(a, 1).MotionHeading.Value);

            List<RenderEntity> b = interp.Sample(1400); // 250 ms past newest, capped at 100
            Near(3f, Find(b, 1).Position.x);
        }

        [Fact]
        public void PastNewest_WithSingleSnapshot_Holds()
        {
            var interp = new SnapshotInterpolator(delayMs: 100);
            interp.Push(S(1, E(1, 768)), 1000);
            RenderEntity r = Find(interp.Sample(5000), 1);
            Near(3f, r.Position.x);
            Assert.Null(r.MotionHeading);
        }
    }
}
