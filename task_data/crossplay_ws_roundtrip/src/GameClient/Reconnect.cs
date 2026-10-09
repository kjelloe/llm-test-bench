using System;
using System.Collections.Generic;

namespace GameClient
{
    /// <summary>Reconnect timing for the Unity client, matching the browser clients.</summary>
    public sealed class ReconnectPolicy
    {
        double _delay = 1;
        bool _connecting;

        // 1 s, then x1.7 (rounded to ms) up to 5 s; the caller waits the returned delay.
        public double NextDelay()
        {
            double delay = _delay;
            _delay = Math.Min(5, Math.Round(_delay * 1.7, 3));
            return delay;
        }

        public void OnConnected() => _delay = 1;

        public bool TryBeginConnect()
        {
            if (_connecting) return false;
            _connecting = true;
            return true;
        }

        public void EndConnect() => _connecting = false;
    }

    /// <summary>The seat token rides the socket URL on reconnect; it must never reach a log.</summary>
    public static class SeatUrl
    {
        public static string WithToken(string url, string token)
        {
            if (string.IsNullOrEmpty(token)) return url;
            var builder = new UriBuilder(url);
            var kept = new List<string>();
            foreach (var part in builder.Query.TrimStart('?').Split('&'))
                if (part != "" && !part.StartsWith("token=", StringComparison.Ordinal)) kept.Add(part);
            kept.Insert(0, "token=" + Uri.EscapeDataString(token));
            builder.Query = string.Join("&", kept);
            return builder.Uri.AbsoluteUri;
        }

        public static string ForLog(string url)
        {
            int cut = url.IndexOfAny(new[] { '?', '#' });
            return cut < 0 ? url : url.Substring(0, cut);
        }
    }
}
