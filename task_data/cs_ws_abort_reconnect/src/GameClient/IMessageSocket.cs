using System.Threading;
using System.Threading.Tasks;

namespace GameClient
{
    /// <summary>A connected WebSocket as the client loop sees it.</summary>
    public interface IMessageSocket
    {
        /// <summary>The next text message, or null when the server closed the connection cleanly.
        /// Throws when the connection fails: IOException / WebSocketException for socket errors, and
        /// OperationCanceledException (or its subclass TaskCanceledException) both when the token is
        /// cancelled AND when Abort() kills the socket while a receive is pending.</summary>
        Task<string> ReceiveAsync(CancellationToken cancellationToken);

        /// <summary>Kill the socket without a close handshake (what a network drop or phone suspend does).</summary>
        void Abort();
    }
}
