using System.Collections.Generic;

namespace GameClient
{
    // A decoded snapshot: one complete view of the world at a server tick. The wire form is
    // {"type":"snapshot","tick":N,"stateHash":...,"view":{"tick":N,...,"events":[...]}}, written by
    // JSON.stringify with "type" first and one "events" array per view ("events":[] when empty).
    public sealed class View
    {
        public int Tick;
        public List<GameEvent> Events = new List<GameEvent>();
    }

    public sealed class GameEvent
    {
        public string Kind;
        public int Unit;
    }
}
