using System;
using System.Collections.Generic;

namespace GameClient
{
    public enum RejectReason
    {
        BadJson,         // not parseable as JSON
        BadShape,        // top level is not an object, or "t" is missing / not a string
        UnknownType,     // "t" names a message type this client does not know
        VersionMismatch, // hello.v outside [MinSupportedVersion, ProtocolVersion]
        BadField         // a required field is missing, has the wrong JSON type, or is out of range
    }

    public sealed class ProtocolException : Exception
    {
        public ProtocolException(RejectReason reason, string message) : base(message)
        {
            Reason = reason;
        }

        public RejectReason Reason { get; }
    }

    public enum PlayerStatus { Alive, Dead, Waiting }

    public sealed class RosterEntry
    {
        public int Id;
        public string Name;
        public int Color;
        public bool Bot;
    }

    /// <summary>Static player identity; sent once in hello, never in snapshots.</summary>
    public sealed class Roster
    {
        public readonly Dictionary<int, RosterEntry> Entries = new Dictionary<int, RosterEntry>();
    }

    public abstract class ServerMessage { }

    public sealed class HelloMessage : ServerMessage
    {
        public int Version;
        public int PlayerId;
        public List<RosterEntry> Roster = new List<RosterEntry>();
    }

    public sealed class RejectMessage : ServerMessage
    {
        public string Reason;
    }

    public sealed class PlayerState
    {
        public int Id;
        public PlayerStatus Status;
        public int X, Y, Dx, Dy;   // fixed-point, 256 units per grid cell
        public int Seq;            // last input sequence the server applied for this player
        public int Cap, Blast, Speed, Remaining, Invulnerable, Kills, Wins, Afk;
        // Identity merged from the roster:
        public string Name;
        public int Color;
        public bool Bot;
    }

    public sealed class BombState
    {
        public int Id, X, Y, Fuse, Blast, Remaining;
    }

    public sealed class SnapMessage : ServerMessage
    {
        public int Tick;
        public string Phase;
        public List<PlayerState> Players = new List<PlayerState>();
        public List<BombState> Bombs = new List<BombState>();
    }
}
