namespace GameClient
{
    /// <summary>An island as the server's JSON view sends it (int fields, like the rest of the wire).</summary>
    public sealed class Island
    {
        public int id, x, y, radius, peak, seed, noiseCell, noiseOctaves, noisePermil, warpCell, warpPermil;
    }
}
