using System;
using System.Collections.Generic;
using System.Text.Json;

namespace Fastengine.Net
{
    public sealed class Session
    {
        readonly IDictionary<string, string> _settings;
        readonly ISet<int> _finalCloseCodes;
        string _url;
        bool _spectate, _welcomed;
        double _retry = 1, _retryAt = -1;
        double _lastArrival = -1;

        public Session(IDictionary<string, string> settings, ISet<int> finalCloseCodes)
        {
            _settings = settings;
            _finalCloseCodes = finalCloseCodes;
        }

        public string State { get; private set; } = "idle";
        public string StopReason { get; private set; }
        public double MaxGap { get; private set; }

        static string Key(string url) => "token:" + new Uri(url).GetLeftPart(UriPartial.Authority);

        string Url()
        {
            if (_spectate) return With(_url, "token", null);
            return With(_url, "token", _settings.TryGetValue(Key(_url), out var t) ? t : null);
        }

        public string Connect(string url, bool spectate, double now)
        {
            _url = url;
            _spectate = spectate;
            _retry = 1;
            _retryAt = -1;
            StopReason = null;
            State = "connecting";
            _welcomed = false;
            _lastArrival = -1;
            return Url();
        }

        public void Opened(double now)
        {
            if (State == "stopped") return;
            State = "open";
            _retry = 1;
            _welcomed = false;
            _lastArrival = -1;
        }

        void Stop(string reason)
        {
            if (State == "stopped") return;
            State = "stopped";
            StopReason = reason;
            _retryAt = -1;
        }

        public void Message(string json, double now)
        {
            if (_lastArrival >= 0) MaxGap = Math.Max(MaxGap, now - _lastArrival);
            _lastArrival = now;
            using var doc = JsonDocument.Parse(json);
            var msg = doc.RootElement;
            string Str(string name) => msg.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
            switch (Str("type"))
            {
                case "welcome":
                    _welcomed = true;
                    var spectator = msg.TryGetProperty("spectator", out var sp) && sp.ValueKind == JsonValueKind.True;
                    var token = Str("token");
                    if (!spectator && !_spectate && !string.IsNullOrEmpty(token)) _settings[Key(_url)] = token;
                    break;
                case "rejected":
                    if (!_welcomed) Stop("refused: " + Str("reason"));
                    break;
                case "kicked":
                    Stop("kicked: " + Str("reason"));
                    break;
            }
        }

        public void Closed(int? code, string reason, double now)
        {
            _lastArrival = -1;
            if (code.HasValue && _finalCloseCodes.Contains(code.Value)) Stop("close " + code.Value);
            if (State == "stopped") return;
            State = "reconnecting";
            _retryAt = now + _retry;
            _retry = Math.Min(5, Math.Round(_retry * 1.7, 3));
        }

        public void QueueOverflow(double now)
        {
            if (State == "stopped") return;
            State = "reconnecting";
            _retryAt = now;
            _lastArrival = -1;
        }

        public string Tick(double now)
        {
            if (State != "reconnecting" || _retryAt < 0 || now < _retryAt) return null;
            _retryAt = -1;
            State = "connecting";
            return Url();
        }

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
