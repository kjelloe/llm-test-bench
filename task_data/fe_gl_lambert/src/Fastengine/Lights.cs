using System.Collections.Generic;
using System.Numerics;

namespace Fastengine
{
    // three.js lights as the browser game builds them (colours are CSS/hex sRGB values, intensities as three r162 takes
    // them). Not editable: the port's job is in Lambert.cs.
    public abstract class Light
    {
        public int Hex;
        public float Intensity;
    }

    public sealed class AmbientLight : Light { public AmbientLight(int hex, float intensity) { Hex = hex; Intensity = intensity; } }

    public sealed class HemisphereLight : Light
    {
        public int GroundHex;
        public HemisphereLight(int skyHex, int groundHex, float intensity) { Hex = skyHex; GroundHex = groundHex; Intensity = intensity; }
    }

    public sealed class DirectionalLight : Light
    {
        public Vector3 Position, Target;
        public DirectionalLight(int hex, float intensity, Vector3 position, Vector3 target)
        {
            Hex = hex; Intensity = intensity; Position = position; Target = target;
        }
    }
}
