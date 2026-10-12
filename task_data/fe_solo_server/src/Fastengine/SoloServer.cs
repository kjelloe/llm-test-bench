using System;
using System.Collections.Generic;

namespace Fastengine
{
    // Single player: the game's own Node server, unchanged, run from the solo folder (solo/solo.json says
    // which file to start, which env to give it with {state} replaced by the state folder, the regex of the
    // line it prints once it accepts connections, and the WebSocket path). It must listen on 127.0.0.1 on a
    // free port the client picks, keep its saves in the state folder, never outlive the client (solo/guard.cjs,
    // preloaded with `node -r`, exits the server when its stdin closes, raising SIGTERM first so it can save),
    // and be stopped on Dispose so that it saves. Its output goes to the log as "[Server] ...".
    // Ready and Failed are raised only from Pump(), which the game calls on its main thread once per frame.
    public sealed class SoloServer : IDisposable
    {
        public SoloServer(string soloDir, string nodePath = "node") => throw new NotImplementedException();

        public event Action<string> Ready;   // the socket URL, ws://127.0.0.1:<port><ws path>
        public event Action<string> Failed;  // a message, e.g. when the server exits on its own

        // The server's process id while it runs, else null.
        public int? Pid => throw new NotImplementedException();

        public void Start(string stateDir, IReadOnlyDictionary<string, string> launchEnv = null) => throw new NotImplementedException();

        public void Pump() => throw new NotImplementedException();

        public void Dispose() => throw new NotImplementedException();
    }
}
