using System;
using System.Collections.Generic;
using System.IO;
using System.Net.WebSockets;
using System.Threading;
using System.Threading.Tasks;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class ConnectionLoopTests
    {
        // Delivers queued messages, then waits until aborted, cancelled, or told to fail/close.
        sealed class FakeSocket : IMessageSocket
        {
            readonly Queue<string> _messages = new Queue<string>();
            readonly TaskCompletionSource<string> _pending = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            public FakeSocket(params string[] messages) { foreach (var m in messages) _messages.Enqueue(m); }
            public bool IgnoresCancellation; // a socket mid-teardown can fail with an IOException instead

            public Task<string> ReceiveAsync(CancellationToken ct)
            {
                if (_messages.Count > 0) return Task.FromResult(_messages.Dequeue());
                if (!IgnoresCancellation) ct.Register(() => _pending.TrySetException(new OperationCanceledException(ct)));
                return _pending.Task;
            }

            // Like ClientWebSocket: aborting a socket with a pending receive surfaces as a cancellation.
            public void Abort() => _pending.TrySetException(new TaskCanceledException("The operation was canceled."));
            public void Fail(Exception e) => _pending.TrySetException(e);
            public void ServerClose() => _pending.TrySetResult(null);
        }

        sealed class Harness
        {
            public readonly List<string> Messages = new List<string>(), Closes = new List<string>();
            public int Reconnects;
            public ConnectionLoop Loop(Func<IMessageSocket> connect) =>
                new ConnectionLoop(connect, Messages.Add, Closes.Add, () => Reconnects++);
        }

        static async Task Finish(Task run) => Assert.True(await Task.WhenAny(run, Task.Delay(5000)) == run, "RunAsync did not finish");

        [Fact]
        public async Task AbortedSocket_IsALostConnection_AndReconnects()
        {
            var h = new Harness();
            var socket = new FakeSocket("hello", "snap");
            Task run = h.Loop(() => socket).RunAsync(CancellationToken.None);
            await Task.Delay(50);
            socket.Abort();
            await Finish(run);
            Assert.Equal(new[] { "hello", "snap" }, h.Messages);
            Assert.Single(h.Closes);
            Assert.Equal(1, h.Reconnects);
        }

        [Fact]
        public async Task AbortedSocket_WithPlainOperationCanceled_AlsoReconnects()
        {
            var h = new Harness();
            var socket = new FakeSocket();
            Task run = h.Loop(() => socket).RunAsync(CancellationToken.None);
            await Task.Delay(50);
            socket.Fail(new OperationCanceledException());
            await Finish(run);
            Assert.Single(h.Closes);
            Assert.Equal(1, h.Reconnects);
        }

        [Fact]
        public async Task ClientShutdown_EndsQuietly_WithoutReconnecting()
        {
            var h = new Harness();
            var socket = new FakeSocket("hello");
            using var cts = new CancellationTokenSource();
            Task run = h.Loop(() => socket).RunAsync(cts.Token);
            await Task.Delay(50);
            cts.Cancel();
            await Finish(run);
            Assert.Equal(new[] { "hello" }, h.Messages);
            Assert.Empty(h.Closes);
            Assert.Equal(0, h.Reconnects);
        }

        [Fact]
        public async Task ShutdownWhileTheSocketFails_StillEndsQuietly()
        {
            var h = new Harness();
            var socket = new FakeSocket { IgnoresCancellation = true };
            using var cts = new CancellationTokenSource();
            Task run = h.Loop(() => socket).RunAsync(cts.Token);
            await Task.Delay(50);
            cts.Cancel();
            socket.Fail(new IOException("socket closed during shutdown"));
            await Finish(run);
            Assert.Empty(h.Closes);
            Assert.Equal(0, h.Reconnects);
        }

        [Fact]
        public async Task ServerClose_IsReported_AndReconnects()
        {
            var h = new Harness();
            var socket = new FakeSocket("a");
            Task run = h.Loop(() => socket).RunAsync(CancellationToken.None);
            await Task.Delay(50);
            socket.ServerClose();
            await Finish(run);
            Assert.Equal(new[] { "closed by server" }, h.Closes);
            Assert.Equal(1, h.Reconnects);
        }

        [Fact]
        public async Task SocketErrors_AreReportedWithTheirMessage_AndReconnect()
        {
            foreach (Exception e in new Exception[] { new IOException("connection reset"), new WebSocketException("remote party closed") })
            {
                var h = new Harness();
                var socket = new FakeSocket();
                Task run = h.Loop(() => socket).RunAsync(CancellationToken.None);
                await Task.Delay(30);
                socket.Fail(e);
                await Finish(run);
                Assert.Equal(new[] { e.Message }, h.Closes);
                Assert.Equal(1, h.Reconnects);
            }
        }

        [Fact]
        public async Task ConnectFailure_IsReported_AndReconnects()
        {
            var h = new Harness();
            await Finish(h.Loop(() => throw new IOException("connection refused")).RunAsync(CancellationToken.None));
            Assert.Equal(new[] { "connection refused" }, h.Closes);
            Assert.Equal(1, h.Reconnects);
        }
    }
}
