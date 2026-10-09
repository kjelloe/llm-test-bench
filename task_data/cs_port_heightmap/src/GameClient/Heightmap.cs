using System;

namespace GameClient
{
    /// <summary>
    /// C# port of CarrierDominion's engine/heightmap.js islandHeightAt and skirtRadius, with what they use
    /// from shared/noise.js, shared/fixed.js and shared/prng.js. The server collides with this terrain
    /// and the Unity client builds its island meshes from it, so heights must equal the JavaScript's.
    /// </summary>
    public static class Heightmap
    {
        public static long SkirtRadius(Island island)
        {
            throw new NotImplementedException();
        }

        public static long IslandHeightAt(Island island, long wx, long wy)
        {
            throw new NotImplementedException();
        }
    }
}
