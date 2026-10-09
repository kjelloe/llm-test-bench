using System;
using System.Threading;
using System.Threading.Tasks;

namespace GameClient
{
    /// <summary>
    /// Runs one game-server connection: connect, deliver messages, and on any loss of the connection
    /// report it and ask for a reconnect. A clean client shutdown (the token passed to RunAsync is
    /// cancelled) must end quietly, without reporting a close or reconnecting.
    /// </summary>
    public sealed class ConnectionLoop
    {
        readonly Func<IMessageSocket> _connect;
        readonly Action<string> _onMessage;
        readonly Action<string> _onClosed;
        readonly Action _requestReconnect;

        public ConnectionLoop(Func<IMessageSocket> connect, Action<string> onMessage, Action<string> onClosed, Action requestReconnect)
        {
            _connect = connect;
            _onMessage = onMessage;
            _onClosed = onClosed;
            _requestReconnect = requestReconnect;
        }

        public async Task RunAsync(CancellationToken shutdown)
        {
            string reason;
            try
            {
                IMessageSocket socket = _connect();
                while (true)
                {
                    string text = await socket.ReceiveAsync(shutdown).ConfigureAwait(false);
                    if (text == null)
                    {
                        reason = "closed by server";
                        break;
                    }
                    _onMessage(text);
                }
            }
            catch (OperationCanceledException)
            {
                return; // shutting down
            }
            catch (Exception e)
            {
                reason = e.Message;
            }
            _onClosed(reason);
            _requestReconnect();
        }
    }
}
