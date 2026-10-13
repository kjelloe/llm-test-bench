using System;
using System.Collections.Generic;
using System.Text.Json;

namespace Fastengine.Net
{
    // The connection policy of a game client (fastengine spec E03, E04, E06), kept apart from the socket so it can be
    // tested without one. The game calls Connect, then reports what the socket does (Opened, Message, Closed,
    // QueueOverflow) with the time on one clock in seconds, and calls Tick every frame; Connect and Tick return the URL
    // to open (Tick returns null when nothing is due).
    //
    // E03, stop rules. A "rejected" message before this connection's "welcome" ends reconnecting (asking again gets
    // the same answer): StopReason "refused: <reason>". After a welcome it is only a status line. "kicked" ends it:
    // StopReason "kicked: <reason>". A close whose code is in the final close codes ends it: "close <code>". Once
    // stopped, State is "stopped" and stays so (no "reconnecting", no retry from Tick) until the next Connect.
    // "halted" changes nothing. Any other close retries: State "reconnecting", the first retry 1 s after the close,
    // each next delay ×1.7 rounded to the millisecond, capped at 5 s, back to 1 s once a connection opens.
    // QueueOverflow (messages were dropped, the state is stale) closes nothing but must reconnect: State
    // "reconnecting" and Tick returns the URL right away.
    //
    // E04, seat tokens. A welcome's non-empty "token" is the seat; it is saved in the settings under
    // "token:<origin>", where origin is the socket URL's scheme, host and port as Uri.GetLeftPart(UriPartial.Authority)
    // writes them (ws://box:8080; a default port is left out), so each server has its own seat. Connect and every reconnect send the saved token for that server as the "token" query parameter
    // (replacing any token in the URL); a spectating connection never sends one, and a spectator's welcome is never
    // saved. The "spectator" field of the welcome says which it is.
    //
    // E06, MaxGap: the largest time between two messages arriving on the same connection, in seconds, over the
    // session. Time spent closed or reconnecting is not a gap (a deliberate drop must not trip the stall metric).
    //
    // State: "idle" before Connect, "connecting" after Connect or a retry until Opened, "open", "reconnecting", "stopped".
    public sealed class Session
    {
        readonly IDictionary<string, string> _settings;
        readonly ISet<int> _finalCloseCodes;
        string _url;
        double _retryAt = -1;
        double _lastArrival = -1;

        public Session(IDictionary<string, string> settings, ISet<int> finalCloseCodes)
        {
            _settings = settings;
            _finalCloseCodes = finalCloseCodes;
        }

        public string State { get; private set; } = "idle";
        public string StopReason { get; private set; }
        public double MaxGap { get; private set; }

        public string Connect(string url, bool spectate, double now)
        {
            _url = url;
            State = "connecting";
            return _url;
        }

        public void Opened(double now) => State = "open";

        public void Message(string json, double now)
        {
            if (_lastArrival >= 0) MaxGap = Math.Max(MaxGap, now - _lastArrival);
            _lastArrival = now;
            using var doc = JsonDocument.Parse(json);
            var msg = doc.RootElement;
            if (msg.GetProperty("type").GetString() == "welcome" && msg.TryGetProperty("token", out var token))
                _settings["token"] = token.GetString();
        }

        public void Closed(int? code, string reason, double now)
        {
            State = "reconnecting";
            _retryAt = now + 1;
        }

        public void QueueOverflow(double now) { }

        public string Tick(double now)
        {
            if (_retryAt < 0 || now < _retryAt) return null;
            _retryAt = -1;
            State = "connecting";
            return _settings.TryGetValue("token", out var t) ? With(_url, "token", t) : _url;
        }

        // The URL with one query parameter set (replaced if present, order otherwise kept), or removed when value is
        // null or empty (fastengine's SocketUrl.With).
        public static string With(string url, string key, string value)
        {
            var builder = new UriBuilder(url);
            var kept = new List<string>();
            foreach (var part in builder.Query.TrimStart('?').Split('&'))
                if (part != "" && part.Split('=')[0] != key) kept.Add(part);
            if (!string.IsNullOrEmpty(value)) kept.Add(key + "=" + Uri.EscapeDataString(value));
            builder.Query = string.Join("&", kept);
            return builder.Uri.AbsoluteUri;
        }
    }
}
