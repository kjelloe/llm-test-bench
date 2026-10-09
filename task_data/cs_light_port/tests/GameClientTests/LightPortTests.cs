using System;
using GameClient;
using UnityEngine;
using Xunit;

namespace GameClientTests
{
    // three.js r162 (physically based lights, colour management on): a hex colour is sRGB and is
    // used in linear space; a Lambert surface reflects albedo * light * intensity / PI. URP's
    // diffuse has no 1/PI. The expected values below follow from that.
    public class LightPortTests
    {
        static Color Lin(uint rgb) => LightPort.FromHex(rgb).linear;

        static void Near(Color expected, Color actual, string what)
        {
            Assert.True(Math.Abs(expected.r - actual.r) < 1e-3 && Math.Abs(expected.g - actual.g) < 1e-3 && Math.Abs(expected.b - actual.b) < 1e-3,
                $"{what}: expected {expected}, got {actual}");
        }

        static void Forward(Vector3 expected, Quaternion q)
        {
            Vector3 f = q * Vector3.forward, e = expected.normalized;
            Assert.True((f - e).magnitude < 1e-4, $"light shines along {f}, expected {e}");
        }

        [Fact]
        public void FromHex_ReadsTheBytes()
        {
            Near(new Color(1f, 0xf2 / 255f, 0xdf / 255f), LightPort.FromHex(0xfff2df), "0xfff2df");
        }

        [Theory]
        [InlineData(1.7f)]
        [InlineData(0.45f)]
        [InlineData(1f)]
        public void DirectionalIntensity_DropsThePhysicalLambertPi(float i)
        {
            Assert.True(Math.Abs(i / Math.PI - LightPort.Intensity(i)) < 1e-6, $"{i} -> {LightPort.Intensity(i)}");
        }

        [Fact]
        public void FlatAmbient_IsScaledInLinearSpace()
        {
            Near((Lin(0xaab4ff) * (1f / Mathf.PI)).gamma, LightPort.AmbientFlat(0xaab4ff, 1.0f), "boombrawl ambient");
            Near((Lin(0x808080) * (0.6f / Mathf.PI)).gamma, LightPort.AmbientFlat(0x808080, 0.6f), "grey ambient");
        }

        [Fact]
        public void Hemisphere_SkyAndGround_AreScaledInLinearSpace()
        {
            var (sky, _, ground) = LightPort.AmbientTrilight(0xbcd8f0, 0x35506a, 2.2f);
            Near((Lin(0xbcd8f0) * (2.2f / Mathf.PI)).gamma, sky, "sky");
            Near((Lin(0x35506a) * (2.2f / Mathf.PI)).gamma, ground, "ground");
        }

        [Fact]
        public void Hemisphere_Equator_IsTheLinearAverage()
        {
            // HemisphereLight mixes sky and ground by 0.5 * dot(n, up) + 0.5: a horizontal normal gets
            // the average of the two LINEAR colours, which is brighter than averaging the sRGB values.
            var (_, equator, _) = LightPort.AmbientTrilight(0xffffff, 0x000000, Mathf.PI);
            Near(new Color(0.5f, 0.5f, 0.5f).gamma, equator, "white over black");
            var (_, eq2, _) = LightPort.AmbientTrilight(0xbcd8f0, 0x35506a, 1.5f);
            Near(((Lin(0xbcd8f0) + Lin(0x35506a)) * (0.5f * 1.5f / Mathf.PI)).gamma, eq2, "carrier dominion equator");
        }

        [Fact]
        public void ZeroIntensity_IsBlack()
        {
            Near(Color.black, LightPort.AmbientFlat(0xaab4ff, 0), "flat");
            var (s, e, g) = LightPort.AmbientTrilight(0xbcd8f0, 0x35506a, 0);
            Near(Color.black, s, "sky"); Near(Color.black, e, "equator"); Near(Color.black, g, "ground");
        }

        [Fact]
        public void DirectionalRotation_ShinesFromThePositionToTheTarget_MirroredIntoUnity()
        {
            Forward(new Vector3(-6, -14, 4), LightPort.DirectionalRotation(new Vector3(6, 14, 4), Vector3.zero));
            const float size = 8000;
            Vector3 centre = new Vector3(size / 2, 0, -size / 2);
            Forward(new Vector3(-0.4f, -0.6f, 0.35f), LightPort.DirectionalRotation(new Vector3(size * 0.9f, size * 0.6f, -size * 0.15f), centre));
            Forward(new Vector3(0.9f, -0.3f, 1.1f), LightPort.DirectionalRotation(new Vector3(-size * 0.4f, size * 0.3f, size * 0.6f), centre));
        }

        [Fact]
        public void ShimSanity_LookRotationFacesForward_AndLinearIsTheSrgbCurve()
        {
            Vector3 d = new Vector3(0.3f, -0.8f, 0.52f).normalized;
            Assert.True((Quaternion.LookRotation(d) * Vector3.forward - d).magnitude < 1e-5);
            Assert.True(Math.Abs(new Color(0.5f, 0.5f, 0.5f).linear.r - 0.21404f) < 1e-4);
        }
    }
}
