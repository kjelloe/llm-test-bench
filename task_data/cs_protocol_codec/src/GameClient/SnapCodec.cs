using System;
using Newtonsoft.Json.Linq;

namespace GameClient
{
    /// <summary>
    /// Client side of the Node server's JSON wire protocol (see Messages.cs for the types).
    /// </summary>
    public sealed class SnapCodec
    {
        public const int ProtocolVersion = 3;
        public const int MinSupportedVersion = 2;

        // Positional row layouts used by "snap". These orders ARE the protocol.
        public static readonly string[] PlayerFields =
        {
            "id", "st", "x", "y", "dx", "dy", "seq", "cap", "blast", "sp", "rem",
            "inv", "kills", "wins", "afk"
        };
        public static readonly string[] BombFields = { "id", "x", "y", "fuse", "blast", "rem" };

        public Roster Roster { get; } = new Roster();

        public ServerMessage Decode(string json)
        {
            throw new NotImplementedException();
        }

        public string EncodeInput(int seq, int dx, int dy, bool bomb)
        {
            throw new NotImplementedException();
        }
    }
}
