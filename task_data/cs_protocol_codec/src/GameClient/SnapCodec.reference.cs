using System;
using System.Collections.Generic;
using Newtonsoft.Json;
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
            JToken root;
            try
            {
                root = JToken.Parse(json);
            }
            catch (JsonException e)
            {
                throw new ProtocolException(RejectReason.BadJson, e.Message);
            }

            if (!(root is JObject obj) || !(obj["t"] is JValue t) || t.Type != JTokenType.String)
                throw new ProtocolException(RejectReason.BadShape, "expected an object with a string 't'");

            switch ((string)t)
            {
                case "hello": return DecodeHello(obj);
                case "snap": return DecodeSnap(obj);
                case "reject": return new RejectMessage { Reason = Str(obj, "reason") };
                default: throw new ProtocolException(RejectReason.UnknownType, "unknown type " + (string)t);
            }
        }

        public string EncodeInput(int seq, int dx, int dy, bool bomb)
        {
            if (seq < 0) throw new ArgumentOutOfRangeException(nameof(seq));
            if (dx < -1 || dx > 1) throw new ArgumentOutOfRangeException(nameof(dx));
            if (dy < -1 || dy > 1) throw new ArgumentOutOfRangeException(nameof(dy));
            if (dx != 0 && dy != 0) throw new ArgumentException("movement is single-axis");

            var o = new JObject { ["t"] = "in", ["seq"] = seq, ["dx"] = dx, ["dy"] = dy };
            if (bomb) o["b"] = 1;
            return o.ToString(Formatting.None);
        }

        HelloMessage DecodeHello(JObject obj)
        {
            int version = Int(obj["v"], "v");
            if (version < MinSupportedVersion || version > ProtocolVersion)
                throw new ProtocolException(RejectReason.VersionMismatch, "unsupported protocol version " + version);

            var hello = new HelloMessage { Version = version, PlayerId = Int(obj["id"], "id") };
            if (!(obj["roster"] is JArray roster))
                throw new ProtocolException(RejectReason.BadField, "roster must be an array");

            foreach (JToken item in roster)
            {
                if (!(item is JObject r))
                    throw new ProtocolException(RejectReason.BadField, "roster entries must be objects");
                hello.Roster.Add(new RosterEntry
                {
                    Id = Int(r["id"], "roster.id"),
                    Name = Str(r, "name"),
                    Color = version >= 3 ? Int(r["color"], "roster.color") : 0,
                    Bot = Int(r["bot"], "roster.bot") != 0
                });
            }

            Roster.Entries.Clear();
            foreach (RosterEntry e in hello.Roster) Roster.Entries[e.Id] = e;
            return hello;
        }

        SnapMessage DecodeSnap(JObject obj)
        {
            var snap = new SnapMessage { Tick = Int(obj["tick"], "tick"), Phase = Str(obj, "phase") };
            foreach (JArray row in Rows(obj, "p", PlayerFields.Length))
            {
                var p = new PlayerState
                {
                    Id = Int(row[0], "p.id"),
                    Status = StatusOf(row[1]),
                    X = Int(row[2], "p.x"), Y = Int(row[3], "p.y"),
                    Dx = Int(row[4], "p.dx"), Dy = Int(row[5], "p.dy"),
                    Seq = Int(row[6], "p.seq"), Cap = Int(row[7], "p.cap"),
                    Blast = Int(row[8], "p.blast"), Speed = Int(row[9], "p.sp"),
                    Remaining = Int(row[10], "p.rem"), Invulnerable = Int(row[11], "p.inv"),
                    Kills = Int(row[12], "p.kills"), Wins = Int(row[13], "p.wins"),
                    Afk = Int(row[14], "p.afk")
                };
                if (Roster.Entries.TryGetValue(p.Id, out RosterEntry who))
                {
                    p.Name = who.Name;
                    p.Color = who.Color;
                    p.Bot = who.Bot;
                }
                else
                {
                    p.Name = "?";
                    p.Color = 0;
                    p.Bot = false;
                }
                snap.Players.Add(p);
            }
            foreach (JArray row in Rows(obj, "b", BombFields.Length))
            {
                snap.Bombs.Add(new BombState
                {
                    Id = Int(row[0], "b.id"), X = Int(row[1], "b.x"), Y = Int(row[2], "b.y"),
                    Fuse = Int(row[3], "b.fuse"), Blast = Int(row[4], "b.blast"),
                    Remaining = Int(row[5], "b.rem")
                });
            }
            return snap;
        }

        static IEnumerable<JArray> Rows(JObject obj, string key, int minLength)
        {
            if (!(obj[key] is JArray rows))
                throw new ProtocolException(RejectReason.BadField, key + " must be an array");
            var result = new List<JArray>();
            foreach (JToken row in rows)
            {
                if (!(row is JArray a) || a.Count < minLength)
                    throw new ProtocolException(RejectReason.BadField, key + " rows need " + minLength + " values");
                result.Add(a);
            }
            return result;
        }

        static PlayerStatus StatusOf(JToken token)
        {
            if (!(token is JValue v) || v.Type != JTokenType.String)
                throw new ProtocolException(RejectReason.BadField, "p.st must be a string");
            switch ((string)v)
            {
                case "a": return PlayerStatus.Alive;
                case "d": return PlayerStatus.Dead;
                default: return PlayerStatus.Waiting;
            }
        }

        static int Int(JToken token, string name)
        {
            if (token is JValue v && v.Type == JTokenType.Integer)
            {
                object raw = v.Value;
                if (raw is long l && l >= int.MinValue && l <= int.MaxValue) return (int)l;
                if (raw is int i) return i;
            }
            throw new ProtocolException(RejectReason.BadField, name + " must be a 32-bit integer");
        }

        static string Str(JObject obj, string name)
        {
            if (obj[name] is JValue v && v.Type == JTokenType.String) return (string)v;
            throw new ProtocolException(RejectReason.BadField, name + " must be a string");
        }
    }
}
