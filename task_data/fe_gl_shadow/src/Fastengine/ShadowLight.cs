using System.Numerics;

namespace Fastengine
{
    // A three.js DirectionalLight with castShadow = true, as the browser game sets it up: the light shines from Position
    // towards Target, and light.shadow carries the orthographic shadow camera (Left..Bottom, Near, Far, in the light's
    // view space), mapSize, bias, normalBias and radius. Defaults are three r162's. Not editable.
    public sealed class ShadowLight
    {
        public Vector3 Position = new Vector3(0, 1, 0), Target = Vector3.Zero;
        public Vector3 Color = Vector3.One;   // linear
        public float Intensity = 1;
        public float Left = -5, Right = 5, Top = 5, Bottom = -5, Near = 0.5f, Far = 500;
        public int MapSize = 512;
        public float Bias, NormalBias, Radius = 1;
    }
}
