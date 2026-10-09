using System;

namespace GameClient
{
    /// <summary>Reconnect timing for the Unity client, matching the browser clients.</summary>
    public sealed class ReconnectPolicy
    {
        public double NextDelay() => throw new NotImplementedException();
        public void OnConnected() => throw new NotImplementedException();
        public bool TryBeginConnect() => throw new NotImplementedException();
        public void EndConnect() => throw new NotImplementedException();
    }

    /// <summary>The seat token rides the socket URL on reconnect; it must never reach a log.</summary>
    public static class SeatUrl
    {
        public static string WithToken(string url, string token) => throw new NotImplementedException();
        public static string ForLog(string url) => throw new NotImplementedException();
    }
}
