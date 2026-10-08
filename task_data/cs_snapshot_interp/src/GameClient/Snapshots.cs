using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    /// <summary>One entity as the authoritative server sent it.</summary>
    public sealed class EntityState
    {
        public int Id;
        public int X;            // fixed-point grid position, 256 units per cell
        public int Y;
        public byte Heading;     // facing in brads: 0..255 = one full turn, 0 = +X, counter-clockwise
        public bool Teleported;  // server moved this entity discontinuously this tick (respawn, warp)
    }

    public sealed class Snapshot
    {
        public int Tick;
        public List<EntityState> Entities = new List<EntityState>();
    }

    /// <summary>What the renderer draws for one entity.</summary>
    public sealed class RenderEntity
    {
        public int Id;
        public Vector3 Position;    // Unity world space, meters: x = X / 256, y = 0, z = Y / 256 (1 cell = 1 m)
        public Quaternion Rotation; // Quaternion.Euler(0, headingBrads * 360 / 256, 0)
        public float? MotionHeading; // direction of travel in radians, Mathf.Atan2(dY, dX); null when not moving
    }
}
