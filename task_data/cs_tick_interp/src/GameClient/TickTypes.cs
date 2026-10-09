using System.Collections.Generic;

namespace GameClient
{
    /// <summary>A thing that moves: engine units (256 per metre), heading in BAM (65536 per turn).</summary>
    public sealed class Mover
    {
        public int id, x, y, z, heading;
    }

    /// <summary>One authoritative view from the server, identified by its simulation tick.</summary>
    public sealed class View
    {
        public int tick;
        public List<Mover> carriers = new List<Mover>();
        public List<Mover> units = new List<Mover>();
    }

    public readonly struct Pose
    {
        public readonly double X, Y, Z, Heading;

        public Pose(double x, double y, double z, double heading)
        {
            X = x; Y = y; Z = z; Heading = heading;
        }
    }

    /// <summary>The newer view of the bracketing pair, with an interpolated pose for every mover in it.</summary>
    public sealed class Sampled
    {
        public View View;
        public readonly Dictionary<int, Pose> Carriers = new Dictionary<int, Pose>();
        public readonly Dictionary<int, Pose> Units = new Dictionary<int, Pose>();
    }
}
