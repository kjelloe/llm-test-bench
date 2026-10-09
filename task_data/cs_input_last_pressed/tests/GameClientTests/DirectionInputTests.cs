using System.Collections.Generic;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    // Input is a static in Unity (and in the shim), so these tests must not run in parallel.
    [Collection("Input")]
    public class DirectionInputTests
    {
        sealed class Rig
        {
            public readonly List<(int, int)> Dirs = new List<(int, int)>();
            public int Bombs, Triggers;
            public readonly DirectionInput Input;

            public Rig()
            {
                UnityEngine.Input.Reset();
                Input = new DirectionInput((dx, dy) => Dirs.Add((dx, dy)), () => Bombs++, () => Triggers++);
            }

            // One frame: the key changes happen, then Update runs, then the frame ends.
            public Rig Frame(KeyCode[] press = null, KeyCode[] release = null)
            {
                foreach (KeyCode k in release ?? new KeyCode[0]) UnityEngine.Input.SimulateRelease(k);
                foreach (KeyCode k in press ?? new KeyCode[0]) UnityEngine.Input.SimulatePress(k);
                Input.Update();
                UnityEngine.Input.NextFrame();
                return this;
            }

            public Rig Press(KeyCode k) => Frame(press: new[] { k });
            public Rig Release(KeyCode k) => Frame(release: new[] { k });
            public Rig Idle(int frames = 3) { for (int i = 0; i < frames; i++) Frame(); return this; }
        }

        [Fact]
        public void PressAndRelease_EmitsTheDirectionThenStop()
        {
            var r = new Rig().Press(KeyCode.D).Idle().Release(KeyCode.D).Idle();
            Assert.Equal(new[] { (1, 0), (0, 0) }, r.Dirs);
        }

        [Fact]
        public void LastPressedWins()
        {
            var r = new Rig().Press(KeyCode.S).Press(KeyCode.W).Press(KeyCode.A).Press(KeyCode.RightArrow).Idle();
            Assert.Equal(new[] { (0, 1), (0, -1), (-1, 0), (1, 0) }, r.Dirs);
        }

        [Fact]
        public void Release_FallsBackToTheMostRecentKeyStillHeld()
        {
            var r = new Rig().Press(KeyCode.D).Press(KeyCode.W).Press(KeyCode.A);
            r.Release(KeyCode.A);
            Assert.Equal((0, -1), r.Dirs[r.Dirs.Count - 1]);
            r.Release(KeyCode.W);
            Assert.Equal((1, 0), r.Dirs[r.Dirs.Count - 1]);
            r.Release(KeyCode.D);
            Assert.Equal(new[] { (1, 0), (0, -1), (-1, 0), (0, -1), (1, 0), (0, 0) }, r.Dirs);
        }

        [Fact]
        public void ReleasingAnOlderKey_ChangesNothing()
        {
            var r = new Rig().Press(KeyCode.D).Press(KeyCode.S).Release(KeyCode.D).Idle();
            Assert.Equal(new[] { (1, 0), (0, 1) }, r.Dirs);
        }

        [Fact]
        public void RepressingAHeldKey_MovesItToTheFront()
        {
            // W held, D pressed, W released and pressed again: W is now the latest.
            var r = new Rig().Press(KeyCode.W).Press(KeyCode.D).Release(KeyCode.W).Press(KeyCode.W).Release(KeyCode.W);
            Assert.Equal(new[] { (0, -1), (1, 0), (0, -1), (1, 0) }, r.Dirs);
        }

        [Fact]
        public void TwoKeysForOneDirection_EmitOnlyOnChange()
        {
            var r = new Rig().Press(KeyCode.W).Press(KeyCode.UpArrow).Release(KeyCode.UpArrow).Idle();
            Assert.Equal(new[] { (0, -1) }, r.Dirs);
            r.Release(KeyCode.W);
            Assert.Equal(new[] { (0, -1), (0, 0) }, r.Dirs);
        }

        [Fact]
        public void BombAndTrigger_FireOncePerPress()
        {
            var r = new Rig().Press(KeyCode.Space).Idle(10).Release(KeyCode.Space).Press(KeyCode.E).Idle(5).Press(KeyCode.R).Idle(5);
            Assert.Equal(2, r.Bombs);
            Assert.Equal(1, r.Triggers);
            Assert.Empty(r.Dirs);
        }

        [Fact]
        public void LosingFocus_ReleasesEverything()
        {
            var r = new Rig().Press(KeyCode.D).Press(KeyCode.W);
            r.Input.OnApplicationFocus(false);
            Assert.Equal((0, 0), r.Dirs[r.Dirs.Count - 1]);
            r.Input.OnApplicationFocus(true);
            r.Idle(5); // D and W are still physically down: no keydown came, so no movement
            Assert.Equal(new[] { (1, 0), (0, -1), (0, 0) }, r.Dirs);
            r.Press(KeyCode.A).Release(KeyCode.A); // falls back to nothing, not to D or W
            Assert.Equal(new[] { (1, 0), (0, -1), (0, 0), (-1, 0), (0, 0) }, r.Dirs);
            r.Release(KeyCode.W).Release(KeyCode.D).Idle();
            Assert.Equal(5, r.Dirs.Count);
        }

        [Fact]
        public void LosingFocus_WhileStill_EmitsNothing()
        {
            var r = new Rig().Idle();
            r.Input.OnApplicationFocus(false);
            r.Input.OnApplicationFocus(true);
            Assert.Empty(r.Dirs);
        }

        [Fact]
        public void UnmappedKeys_AreIgnored()
        {
            var r = new Rig().Press(KeyCode.D).Press(KeyCode.Q).Release(KeyCode.Q).Press(KeyCode.Alpha1).Idle();
            Assert.Equal(new[] { (1, 0) }, r.Dirs);
        }
    }
}
