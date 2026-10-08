using System;
using System.Collections.Generic;
using System.Threading;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class MainThreadDispatcherTests
    {
        static void RunOnNewThread(Action body)
        {
            Exception error = null;
            var t = new Thread(() =>
            {
                try { body(); }
                catch (Exception e) { error = e; }
            });
            t.Start();
            Assert.True(t.Join(5000), "worker thread did not finish (deadlock?)");
            if (error != null) throw new Exception("worker thread failed", error);
        }

        static void RunWorkers(int count, Action<int> body)
        {
            var start = new Barrier(count);
            var errors = new List<Exception>();
            var workers = new Thread[count];
            for (int t = 0; t < count; t++)
            {
                int index = t;
                workers[t] = new Thread(() =>
                {
                    try
                    {
                        start.SignalAndWait();
                        body(index);
                    }
                    catch (Exception e)
                    {
                        lock (errors) errors.Add(e);
                    }
                });
                workers[t].Start();
            }
            foreach (var w in workers) Assert.True(w.Join(10000), "worker thread did not finish");
            Assert.True(errors.Count == 0, errors.Count == 0 ? "" : "worker failed: " + errors[0]);
        }

        [Fact]
        public void Constructor_RejectsInvalidLimits()
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => new MainThreadDispatcher(0, 10));
            Assert.Throws<ArgumentOutOfRangeException>(() => new MainThreadDispatcher(10, 0));
        }

        [Fact]
        public void Enqueue_Null_Throws()
        {
            var d = new MainThreadDispatcher(10, 10);
            Assert.Throws<ArgumentNullException>(() => d.Enqueue(null));
        }

        [Fact]
        public void Drain_RunsFifo_UpToPerFrameBudget()
        {
            var d = new MainThreadDispatcher(100, 4);
            var order = new List<int>();
            for (int i = 0; i < 10; i++)
            {
                int n = i;
                Assert.True(d.Enqueue(() => order.Add(n)));
            }

            Assert.Equal(4, d.Drain());
            Assert.Equal(new[] { 0, 1, 2, 3 }, order);
            Assert.Equal(6, d.Pending);
            Assert.Equal(4, d.Drain());
            Assert.Equal(2, d.Drain());
            Assert.Equal(0, d.Drain());
            Assert.Equal(new[] { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 }, order);
        }

        [Fact]
        public void Enqueue_WhenFull_RejectsNewestAndCountsDrop()
        {
            var d = new MainThreadDispatcher(3, 10);
            var ran = new List<string>();
            Assert.True(d.Enqueue(() => ran.Add("a")));
            Assert.True(d.Enqueue(() => ran.Add("b")));
            Assert.True(d.Enqueue(() => ran.Add("c")));
            Assert.False(d.Enqueue(() => ran.Add("d")));
            Assert.Equal(1, d.DroppedCount);
            Assert.Equal(3, d.Pending);

            Assert.Equal(3, d.Drain());
            Assert.Equal(new[] { "a", "b", "c" }, ran);
            Assert.True(d.Enqueue(() => ran.Add("e")));
        }

        [Fact]
        public void ConcurrentEnqueue_LosesNothing()
        {
            const int threads = 8, perThread = 5000;
            var d = new MainThreadDispatcher(threads * perThread, 1000);
            long sum = 0;
            int ran = 0;
            RunWorkers(threads, t =>
            {
                int offset = t * perThread;
                for (int i = 0; i < perThread; i++)
                {
                    long v = offset + i;
                    if (!d.Enqueue(() => { sum += v; ran++; }))
                        throw new Exception("unexpected drop");
                }
            });

            Assert.Equal(threads * perThread, d.Pending);
            while (d.Drain() > 0) { }
            long n = threads * perThread;
            Assert.Equal(threads * perThread, ran);
            Assert.Equal(n * (n - 1) / 2, sum);
            Assert.Equal(0, d.DroppedCount);
        }

        [Fact]
        public void ConcurrentEnqueue_RespectsCapacityExactly()
        {
            const int threads = 8, perThread = 500;
            var d = new MainThreadDispatcher(1000, 100);
            int accepted = 0;
            RunWorkers(threads, t =>
            {
                for (int i = 0; i < perThread; i++)
                    if (d.Enqueue(() => { })) Interlocked.Increment(ref accepted);
            });

            Assert.Equal(1000, accepted);
            Assert.Equal(1000, d.Pending);
            Assert.Equal(threads * perThread - 1000, d.DroppedCount);
        }

        [Fact]
        public void WorkEnqueuedDuringDrain_RunsOnNextDrain()
        {
            var d = new MainThreadDispatcher(10, 10);
            var ran = new List<string>();
            d.Enqueue(() =>
            {
                ran.Add("first");
                d.Enqueue(() => ran.Add("second"));
            });

            Assert.Equal(1, d.Drain());
            Assert.Equal(new[] { "first" }, ran);
            Assert.Equal(1, d.Pending);
            Assert.Equal(1, d.Drain());
            Assert.Equal(new[] { "first", "second" }, ran);
        }

        [Fact]
        public void ThrowingAction_DoesNotStopDrain()
        {
            var d = new MainThreadDispatcher(10, 10);
            var ran = new List<int>();
            d.Enqueue(() => ran.Add(1));
            d.Enqueue(() => throw new InvalidOperationException("boom"));
            d.Enqueue(() => ran.Add(3));

            Assert.Equal(3, d.Drain());
            Assert.Equal(new[] { 1, 3 }, ran);
            Assert.Equal(1, d.ExceptionCount);
            Assert.Equal(0, d.Pending);
        }

        [Fact]
        public void ThrowingActions_CountTowardBudget()
        {
            var d = new MainThreadDispatcher(10, 2);
            d.Enqueue(() => throw new Exception("x"));
            d.Enqueue(() => throw new Exception("y"));
            d.Enqueue(() => { });
            Assert.Equal(2, d.Drain());
            Assert.Equal(1, d.Pending);
            Assert.Equal(2, d.ExceptionCount);
        }

        [Fact]
        public void ActionsRunWithoutBlockingOtherThreads()
        {
            var d = new MainThreadDispatcher(10, 10);
            bool otherThreadEnqueued = false;
            d.Enqueue(() => RunOnNewThread(() => otherThreadEnqueued = d.Enqueue(() => { })));

            Assert.Equal(1, d.Drain());
            Assert.True(otherThreadEnqueued);
            Assert.Equal(1, d.Pending);
        }

        [Fact]
        public void Drain_FromAnotherThread_AfterBinding_Throws()
        {
            var d = new MainThreadDispatcher(10, 10);
            d.Drain();
            Exception caught = null;
            RunOnNewThread(() =>
            {
                try { d.Drain(); }
                catch (Exception e) { caught = e; }
            });
            Assert.IsType<InvalidOperationException>(caught);
        }
    }
}
