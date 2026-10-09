using System;
using System.Collections.Generic;
using System.Linq;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class ReconnectTests
    {
        // Decoded the way the game server reads it (Node's URLSearchParams): '+' is a space.
        static string Decode(string s) => Uri.UnescapeDataString(s.Replace('+', ' '));

        static Dictionary<string, string> Query(string url)
        {
            var q = new Uri(url).Query.TrimStart('?');
            return q.Split('&', StringSplitOptions.RemoveEmptyEntries)
                .Select(p => p.Split('=', 2))
                .ToDictionary(kv => Decode(kv[0]), kv => kv.Length > 1 ? Decode(kv[1]) : "");
        }

        [Fact]
        public void Delays_StartAtOneSecond_GrowBy1_7_CapAtFive()
        {
            var p = new ReconnectPolicy();
            Assert.Equal(new[] { 1.0, 1.7, 2.89, 4.913, 5.0, 5.0 }, Enumerable.Range(0, 6).Select(_ => p.NextDelay()).ToArray());
        }

        [Fact]
        public void Connecting_ResetsTheDelay()
        {
            var p = new ReconnectPolicy();
            p.NextDelay(); p.NextDelay(); p.NextDelay();
            p.OnConnected();
            Assert.Equal(1.0, p.NextDelay());
            Assert.Equal(1.7, p.NextDelay());
        }

        [Fact]
        public void ConnectsNeverOverlap()
        {
            var p = new ReconnectPolicy();
            Assert.True(p.TryBeginConnect());
            Assert.False(p.TryBeginConnect());
            p.EndConnect();
            Assert.True(p.TryBeginConnect());
        }

        [Fact]
        public void WithToken_AddsTheToken_KeepsPathPortAndOtherParams()
        {
            string url = SeatUrl.WithToken("ws://10.0.0.5:8080/ws?join=AB12-CD34&spectate=0", "tok123");
            var u = new Uri(url);
            Assert.Equal("ws", u.Scheme);
            Assert.Equal(8080, u.Port);
            Assert.Equal("/ws", u.AbsolutePath);
            var q = Query(url);
            Assert.Equal("tok123", q["token"]);
            Assert.Equal("AB12-CD34", q["join"]);
            Assert.Equal("0", q["spectate"]);
        }

        [Fact]
        public void WithToken_ReplacesAnExistingToken()
        {
            string url = SeatUrl.WithToken("ws://host/ws?token=old&join=X", "new");
            Assert.Equal("new", Query(url)["token"]);
            Assert.Equal(1, new Uri(url).Query.Split("token=").Length - 1);
        }

        [Theory]
        [InlineData("a+b")]
        [InlineData("x&admin=1")]
        [InlineData("k=v/w")]
        [InlineData("with space")]
        [InlineData("%2Fpre-escaped")]
        public void WithToken_EscapesTheTokenSoItRoundTripsExactly(string token)
        {
            string url = SeatUrl.WithToken("wss://games.example/ws?join=Q", token);
            var q = Query(url);
            Assert.Equal(token, q["token"]);
            Assert.Equal("Q", q["join"]);
            Assert.False(q.ContainsKey("admin"), "token text leaked into a separate query parameter");
        }

        [Fact]
        public void EmptyToken_LeavesTheUrlUnchanged()
        {
            Assert.Equal("ws://host:8080/ws?join=X", SeatUrl.WithToken("ws://host:8080/ws?join=X", ""));
        }

        [Fact]
        public void ForLog_StripsQueryAndFragment()
        {
            Assert.Equal("ws://host:8080/ws", SeatUrl.ForLog("ws://host:8080/ws?token=secret&join=X"));
            Assert.Equal("wss://h/ws", SeatUrl.ForLog("wss://h/ws#token=secret"));
            Assert.Equal("ws://h/ws", SeatUrl.ForLog("ws://h/ws"));
            Assert.DoesNotContain("secret", SeatUrl.ForLog(SeatUrl.WithToken("ws://h/ws", "secret")));
        }
    }
}
