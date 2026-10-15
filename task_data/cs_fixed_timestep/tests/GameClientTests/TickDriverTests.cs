using System;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class TickDriverTests
    {
        static (TickDriver driver, Func<int> count) Make()
        {
            var n = 0;
            return (new TickDriver(() => n++), () => n);
        }

        // Expected ticks for a run of frames: every whole TickSeconds of real time, computed exactly in double.
        static long Expected(float frame, int frames)
        {
            double t = 0;
            for (var i = 0; i < frames; i++) t += frame;
            return (long)Math.Floor(t / TickDriver.TickSeconds + 1e-9);
        }

        [Theory]
        [InlineData(30)]
        [InlineData(60)]
        [InlineData(144)]
        [InlineData(15)]
        public void TickRate_DoesNotDependOnFrameRate(int fps)
        {
            var (d, count) = Make();
            var frame = 1f / fps;
            var frames = (int)(120.01 * fps);
            for (var i = 0; i < frames; i++) d.Frame(frame);
            Assert.Equal(Expected(frame, frames), count());
            Assert.Equal(count(), d.Ticks);
        }

        [Fact]
        public void JitteryFrames_RunEveryTickThatFellDue()
        {
            var (d, count) = Make();
            var rng = new Random(7);
            double t = 0;
            for (var i = 0; i < 20000; i++)
            {
                var f = (float)(0.004 + rng.NextDouble() * 0.09);
                t += f;
                d.Frame(f);
                Assert.Equal((long)Math.Floor(t / TickDriver.TickSeconds + 1e-9), d.Ticks);
            }
        }

        [Fact]
        public void OneHourAt144Fps_NoDrift()
        {
            var (d, _) = Make();
            const int frames = 144 * 3600;
            var frame = 1f / 144;
            for (var i = 0; i < frames; i++) d.Frame(frame);
            Assert.Equal(Expected(frame, frames), d.Ticks);
        }

        [Fact]
        public void LongFrame_RunsSeveralTicks_AndKeepsTheRemainder()
        {
            var (d, count) = Make();
            d.Frame(0.125f);
            Assert.Equal(2, count());
            Assert.InRange(d.Alpha, 0.49f, 0.51f);
            d.Frame(0.03125f);
            Assert.Equal(3, count());
            Assert.InRange(d.Alpha, 0.12f, 0.13f);
        }

        [Fact]
        public void Hitch_IsCapped_AndTheBacklogIsDropped()
        {
            var (d, count) = Make();
            d.Frame(2.0f);
            Assert.Equal(TickDriver.MaxTicksPerFrame, count());
            Assert.Equal(0f, d.Alpha);   // the backlog beyond the cap is dropped, not carried over
            for (var i = 0; i < 4; i++) d.Frame(0.01f);
            Assert.Equal(TickDriver.MaxTicksPerFrame, count());
            for (var i = 0; i < 100; i++) d.Frame(1f / 60);
            Assert.InRange(count(), TickDriver.MaxTicksPerFrame + 33, TickDriver.MaxTicksPerFrame + 34);
        }

        [Fact]
        public void Alpha_GrowsThroughATick()
        {
            var (d, _) = Make();
            var last = -1f;
            for (var i = 0; i < 4; i++)
            {
                d.Frame(0.01f);
                Assert.True(d.Alpha > last);
                Assert.InRange(d.Alpha, 0f, 1f);
                last = d.Alpha;
            }
            Assert.InRange(d.Alpha, 0.79f, 0.81f);
        }

        [Theory]
        [InlineData(0f)]
        [InlineData(-0.5f)]
        [InlineData(float.NaN)]
        [InlineData(float.PositiveInfinity)]
        public void BadDeltas_AreIgnored(float delta)
        {
            var (d, count) = Make();
            d.Frame(0.03f);
            d.Frame(delta);
            d.Frame(0.03f);
            Assert.Equal(1, count());
            Assert.InRange(d.Alpha, 0.19f, 0.21f);
        }

        [Fact]
        public void Pause_StopsTicks_AndResumeDoesNotReplayTheGap()
        {
            var (d, count) = Make();
            for (var i = 0; i < 6; i++) d.Frame(0.025f);
            Assert.Equal(3, count());
            d.Pause(true);
            d.Frame(0.5f);
            Assert.Equal(3, count());
            d.Pause(false);
            d.Frame(30f);   // Unity's first delta after a pause spans the whole pause
            Assert.Equal(3, count());
            d.Frame(0.05f);
            Assert.Equal(4, count());
        }

        [Fact]
        public void PauseTwice_ThenResume_SkipsOnlyOneFrame()
        {
            var (d, count) = Make();
            d.Pause(true);
            d.Pause(true);
            d.Pause(false);
            d.Pause(false);
            d.Frame(10f);
            d.Frame(0.05f);
            Assert.Equal(1, count());
        }

        [Fact]
        public void ResumeWithoutAPause_DropsNothing()
        {
            // Unity calls OnApplicationFocus(true) at startup, before any pause.
            var (d, count) = Make();
            d.Pause(false);
            d.Frame(0.05f);
            Assert.Equal(1, count());
        }

        // The point of the whole class: the same inputs give the same game state at any frame rate.
        [Fact]
        public void SameSimulation_At30_60_144Fps()
        {
            long Run(int fps)
            {
                long state = 1;
                var d = new TickDriver(() => state = (state * 6364136223846793005L + 1442695040888963407L));
                var frame = 1f / fps;
                for (var i = 0; i < (int)(30.01 * fps); i++) d.Frame(frame);
                return state;
            }
            var a = Run(30);
            Assert.Equal(a, Run(60));
            Assert.Equal(a, Run(144));
        }
    }
}
