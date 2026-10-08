using System.Collections.Generic;

namespace GameClient
{
    /// <summary>Sent to the server once per client tick: {"t":"in","seq":..,"dx":..,"dy":..}.</summary>
    public sealed class InputCommand
    {
        public int Seq;
        public int Dx;
        public int Dy;
    }

    public sealed class PlayerSnapshot
    {
        public int Id;
        public string Status;   // "alive", "dead" or "waiting"
        public int X;
        public int Y;
        public int Seq;         // highest input seq the server has applied for this player
        public int SpeedLevel;  // speed power-ups collected; see Movement.SpeedForLevel
    }

    public sealed class AuthoritativeSnapshot
    {
        public int Tick;
        public string Phase;    // "lobby", "play" or "over"
        public List<PlayerSnapshot> Players = new List<PlayerSnapshot>();
    }
}
