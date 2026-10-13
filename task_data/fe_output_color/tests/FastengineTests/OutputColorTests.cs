using System.Text.Json;
using Fastengine.Three;
using Xunit;

namespace FastengineTests
{
    // Fixtures are pixels three r162 itself wrote in headless Chromium (tools/make_fixtures.reference.mjs): an unlit
    // MeshBasicMaterial plane filling the view at the given depth, read back as 8-bit RGB.
    public class OutputColorTests
    {
        static readonly JsonElement[] Cases = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures.json")))
            .RootElement.EnumerateArray().ToArray();

        public static IEnumerable<object[]> Names() => Cases.Select(c => new object[] { c.GetProperty("name").GetString() });

        static double[] D(JsonElement e) => e.EnumerateArray().Select(x => x.GetDouble()).ToArray();

        [Theory]
        [MemberData(nameof(Names))]
        public void MatchesThree(string name)
        {
            var c = Cases.Single(x => x.GetProperty("name").GetString() == name);
            var s = new OutputSettings
            {
                ToneMapping = Enum.Parse<ToneMappingMode>(c.GetProperty("toneMapping").GetString(), true),
                Exposure = c.GetProperty("exposure").GetDouble(),
                ToScreen = c.GetProperty("toScreen").GetBoolean(),
                Fog = c.GetProperty("fog").GetString() switch { "Exp2" => FogMode.Exp2, "Linear" => FogMode.Linear, _ => FogMode.None },
                FogColor = D(c.GetProperty("fogColor")),
                FogNear = c.GetProperty("fogNear").GetDouble(),
                FogFar = c.GetProperty("fogFar").GetDouble(),
                FogDensity = c.GetProperty("fogDensity").GetDouble(),
            };
            var got = OutputColor.Fragment(D(c.GetProperty("color")), c.GetProperty("depth").GetDouble(), s,
                c.GetProperty("toneMapped").GetBoolean(), c.GetProperty("materialFog").GetBoolean());
            var want = c.GetProperty("rgb").EnumerateArray().Select(x => x.GetInt32()).ToArray();
            var bytes = got.Select(v => (int)Math.Round(Math.Clamp(v, 0, 1) * 255)).ToArray();
            for (int i = 0; i < 3; i++)
                Assert.True(Math.Abs(bytes[i] - want[i]) <= 1, $"{name}: ({string.Join(", ", bytes)}), three wrote ({string.Join(", ", want)})");
        }
    }
}
