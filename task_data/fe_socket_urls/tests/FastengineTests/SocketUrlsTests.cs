using Fastengine;
using Fastengine.Net;
using Xunit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace FastengineTests
{
    public class SocketUrlsTests
    {
        const string Refusal = "protocol 2 required, client has 0";

        [Fact]
        public void With_AddsReplacesAndRemoves()
        {
            Assert.Equal("ws://h:1/ws?proto=1", SocketUrl.With("ws://h:1/ws", "proto", "1"));
            Assert.Equal("ws://h:1/ws?a=2&proto=1", SocketUrl.With("ws://h:1/ws?a=2&proto=0", "proto", "1"));
            Assert.Equal("ws://h:1/ws?a=2&b=3&proto=1", SocketUrl.With("ws://h:1/ws?a=2&proto=0&b=3", "proto", "1"));
            Assert.Equal("ws://h:1/ws?a=2", SocketUrl.With("ws://h:1/ws?spectate=1&a=2", "spectate", ""));
            Assert.Equal("ws://h:1/ws?a=2", SocketUrl.With("ws://h:1/ws?spectate=1&a=2", "spectate", null));
            Assert.Equal("ws://h:1/ws", SocketUrl.With("ws://h:1/ws?spectate=1", "spectate", null));
        }

        [Fact]
        public void With_MatchesTheWholeKeyOnly()
        {
            Assert.Equal("ws://h/ws?protocol=7&proto=1", SocketUrl.With("ws://h/ws?protocol=7", "proto", "1"));
            Assert.Equal("ws://h/ws?xproto=3", SocketUrl.With("ws://h/ws?xproto=3&proto=2", "proto", ""));
        }

        [Fact]
        public void With_EscapesTheValue()
        {
            Assert.Equal("wss://h/ws?code=a%20b%26c", SocketUrl.With("wss://h/ws", "code", "a b&c"));
            Assert.Equal("wss://h/ws?name=%C3%A6%C3%B8%C3%A5%3D%2B", SocketUrl.With("wss://h/ws", "name", "æøå=+"));
        }

        [Fact]
        public void PageFor_TheDownloadPageOnTheSameOrigin()
        {
            Assert.Equal("https://bb.example.org/native", UpdateNotice.PageFor(Refusal, "wss://bb.example.org/ws?proto=0&token=t"));
            Assert.Equal("http://127.0.0.1:8080/native", UpdateNotice.PageFor(Refusal, "ws://127.0.0.1:8080/?proto=0"));
            Assert.Equal("https://h/native", UpdateNotice.PageFor(Refusal, "wss://h:443/"));
            Assert.Equal("http://h/native", UpdateNotice.PageFor(Refusal, "ws://h:80/game#x"));
            Assert.Equal("https://h:8443/native", UpdateNotice.PageFor("protocol 12 required, client has 11", "wss://h:8443/a/b"));
        }

        [Fact]
        public void PageFor_OnlyForTheProtocolRefusal()
        {
            Assert.Null(UpdateNotice.PageFor("the table does not take observers", "ws://h/"));
            Assert.Null(UpdateNotice.PageFor(null, "ws://h/"));
            Assert.Null(UpdateNotice.PageFor("refused: protocol 2 required", "ws://h/"));
            Assert.Null(UpdateNotice.PageFor("protocol x required", "ws://h/"));
            Assert.Null(UpdateNotice.PageFor("protocol 2 requiredness", "ws://h/"));
        }

        [Fact]
        public void For_TheLineToShow_AndOneLogLine()
        {
            int before = Log.Snapshot().Length;
            Assert.Equal("A newer version is out: http://h/native", UpdateNotice.For(Refusal, "ws://h/"));
            Assert.Null(UpdateNotice.For("kicked", "ws://h/"));
            var logged = Log.Snapshot().Skip(before).ToArray();
            Assert.Equal(new[] { "[Net] update needed http://h/native" }, logged);
        }
    }
}
