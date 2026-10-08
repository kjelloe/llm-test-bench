using System.Collections.Generic;

namespace GameClient
{
    public sealed class UnitState
    {
        public uint Id;
        public byte Team;
        public int X;           // fixed-point, 256 units per cell
        public int Y;
        public byte Heading;    // brads
        public ushort Hp;
        public bool Alive;
        public uint? Target;    // id of the unit being attacked, or null
        public string Name;
    }

    public sealed class GameState
    {
        public uint Tick;
        public List<UnitState> Units = new List<UnitState>();
    }
}
