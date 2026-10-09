using System;

namespace GameClient
{
    // The Unity client's connection to the match server (see the task description for the wire messages).
    // Uses WebSocketConnection (blocking RFC 6455 client) on its own background thread, and ReconnectPolicy
    // and SeatUrl from Reconnect.cs. Every member here may be called from any thread.
    public sealed class SeatClient : IDisposable
    {
        public SeatClient(string serverUrl) => throw new NotImplementedException();

        public void Start() => throw new NotImplementedException();

        public int Team => throw new NotImplementedException();          // -1 until the first welcome
        public bool Connected => throw new NotImplementedException();    // welcomed on the current socket
        public bool Superseded => throw new NotImplementedException();   // closed with 4000: stopped for good
        public int AckedSeq => throw new NotImplementedException();      // highest seq the server acked
        public int Welcomes => throw new NotImplementedException();      // welcomes received so far

        // Queues a command (any JSON value) and returns its seq (1, 2, 3, ... for the life of the client).
        public int SendCommand(string commandJson) => throw new NotImplementedException();

        public void Dispose() => throw new NotImplementedException();
    }
}
