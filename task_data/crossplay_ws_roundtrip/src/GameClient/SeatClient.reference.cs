using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace GameClient
{
    // The Unity client's connection to the match server (see the task description for the wire messages).
    // Uses WebSocketConnection (blocking RFC 6455 client) on its own background thread, and ReconnectPolicy
    // and SeatUrl from Reconnect.cs. Every member here may be called from any thread.
    public sealed class SeatClient : IDisposable
    {
        readonly string _url;
        readonly object _gate = new object();
        readonly List<(int seq, string json)> _unacked = new List<(int, string)>();
        readonly ReconnectPolicy _policy = new ReconnectPolicy();
        readonly ManualResetEventSlim _stopped = new ManualResetEventSlim(false);
        WebSocketConnection _ws;   // set once welcomed, under _gate
        WebSocketConnection _current; // the socket being read, for Dispose
        string _token = "";
        int _nextSeq = 1;
        Thread _thread;

        int _team = -1, _acked, _welcomes;
        volatile bool _connected, _superseded;

        public SeatClient(string serverUrl) => _url = serverUrl;

        public void Start()
        {
            _thread = new Thread(Run) { IsBackground = true, Name = "SeatClient" };
            _thread.Start();
        }

        public int Team => Volatile.Read(ref _team);
        public bool Connected => _connected;
        public bool Superseded => _superseded;
        public int AckedSeq => Volatile.Read(ref _acked);
        public int Welcomes => Volatile.Read(ref _welcomes);

        public int SendCommand(string commandJson)
        {
            lock (_gate)
            {
                int seq = _nextSeq++;
                _unacked.Add((seq, commandJson));
                // Before the welcome, or while reconnecting, it waits in the queue and goes out on the next welcome.
                if (_ws != null) TrySend(_ws, seq, commandJson);
                return seq;
            }
        }

        static void TrySend(WebSocketConnection ws, int seq, string json)
        {
            try { ws.SendText("{\"type\":\"command\",\"seq\":" + seq + ",\"cmd\":" + json + "}"); }
            catch (IOException) { } // the reader sees the drop and reconnects; the command stays queued
            catch (ObjectDisposedException) { }
        }

        void Run()
        {
            while (!_stopped.IsSet)
            {
                WebSocketConnection ws = null;
                try
                {
                    ws = new WebSocketConnection(new Uri(SeatUrl.WithToken(_url, _token)), 1 << 20);
                    lock (_gate) _current = ws;
                    if (_stopped.IsSet) break;
                    while (!_stopped.IsSet)
                    {
                        byte[] bytes = ws.ReadMessage(out string closeReason);
                        if (bytes == null)
                        {
                            if (closeReason != null && closeReason.StartsWith("4000", StringComparison.Ordinal))
                            {
                                _superseded = true;
                                _stopped.Set();
                            }
                            break;
                        }
                        Handle(ws, Encoding.UTF8.GetString(bytes));
                    }
                }
                catch (IOException) { }
                catch (SocketException) { }
                catch (ObjectDisposedException) { }
                finally
                {
                    lock (_gate) _ws = null;
                    _connected = false;
                    ws?.Dispose();
                }
                if (_stopped.IsSet) break;
                _stopped.Wait(TimeSpan.FromSeconds(_policy.NextDelay()));
            }
        }

        void Handle(WebSocketConnection ws, string text)
        {
            string type = Field(text, "type");
            if (type == "welcome")
            {
                lock (_gate)
                {
                    _token = Field(text, "token");
                    Volatile.Write(ref _team, int.Parse(Field(text, "team")));
                    Interlocked.Increment(ref _welcomes);
                    _policy.OnConnected();
                    _ws = ws;
                    _connected = true;
                    foreach (var (seq, json) in _unacked) TrySend(ws, seq, json); // in order, before anything newer
                }
            }
            else if (type == "ack")
            {
                int seq = int.Parse(Field(text, "seq"));
                lock (_gate)
                {
                    _unacked.RemoveAll(c => c.seq <= seq);
                    if (seq > _acked) Volatile.Write(ref _acked, seq);
                }
            }
        }

        static string Field(string json, string name)
        {
            Match m = Regex.Match(json, "\"" + name + "\":(?:\"([^\"]*)\"|(-?\\d+|true|false))");
            return !m.Success ? "" : m.Groups[1].Success ? m.Groups[1].Value : m.Groups[2].Value;
        }

        public void Dispose()
        {
            _stopped.Set();
            WebSocketConnection ws;
            lock (_gate) ws = _current;
            ws?.Abort();
            _thread?.Join(TimeSpan.FromSeconds(5));
        }
    }
}
