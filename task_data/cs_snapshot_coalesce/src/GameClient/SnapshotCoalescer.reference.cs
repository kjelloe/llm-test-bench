using System;

namespace GameClient
{
    // Main-thread side of the Unity client's message handling. At x16 time compression the server sends
    // 320 complete views a second in bursts; parsing every one costs frames, so only the newest view per
    // frame should be parsed and applied. The UI (sound, console log) still needs every view's events.
    public sealed class SnapshotCoalescer
    {
        const string SnapshotPrefix = "{\"type\":\"snapshot\"";
        const string WelcomePrefix = "{\"type\":\"welcome\"";
        const string NoEvents = "\"events\":[]";

        readonly Func<string, View> _parse;
        readonly Action<View> _apply;
        readonly Action<View> _events;
        readonly Action<string> _other;
        string _pending;

        // parse: decodes a snapshot message (expensive). apply: draw this view. events: show a view's events.
        // other: any message that is not a snapshot.
        public SnapshotCoalescer(Func<string, View> parse, Action<View> apply, Action<View> events, Action<string> other)
        {
            _parse = parse;
            _apply = apply;
            _events = events;
            _other = other;
        }

        // Called for every message, in arrival order.
        public void OnMessage(string text)
        {
            if (text.StartsWith(SnapshotPrefix, StringComparison.Ordinal))
            {
                // The view being replaced is never drawn, but its events still happened.
                if (_pending != null && !_pending.Contains(NoEvents)) _events(_parse(_pending));
                _pending = text;
                return;
            }
            if (text.StartsWith(WelcomePrefix, StringComparison.Ordinal)) _pending = null; // a new match
            _other(text);
        }

        // Called once per frame, before drawing.
        public void Flush()
        {
            if (_pending == null) return;
            View view = _parse(_pending);
            _pending = null;
            _apply(view);
            if (view.Events.Count > 0) _events(view);
        }
    }
}
