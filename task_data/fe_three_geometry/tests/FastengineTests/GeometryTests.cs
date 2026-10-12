using System.Text.Json;
using Fastengine.Three;
using Xunit;

namespace FastengineTests
{
    // Fixtures are three's own output (js/make-fixtures.mjs runs js/three/*.js, three 0.165.0) for each case.
    public class GeometryTests
    {
        static readonly JsonElement[] Cases = Load();

        static JsonElement[] Load()
        {
            var path = Path.Combine(AppContext.BaseDirectory, "fixtures.json");
            return JsonDocument.Parse(File.ReadAllText(path)).RootElement.EnumerateArray().ToArray();
        }

        public static IEnumerable<object[]> Names() => Cases.Select(c => new object[] { c.GetProperty("name").GetString() });

        static GeometryData Build(JsonElement c)
        {
            var a = c.GetProperty("args").EnumerateArray().ToArray();
            float F(int i) => (float)a[i].GetDouble();
            int I(int i) => a[i].GetInt32();
            bool B(int i) => a[i].GetBoolean();
            return c.GetProperty("kind").GetString() switch
            {
                "Box" => a.Length == 3 ? Geometries.Box(F(0), F(1), F(2)) : Geometries.Box(F(0), F(1), F(2), I(3), I(4), I(5)),
                "Cylinder" => Geometries.Cylinder(F(0), F(1), F(2), I(3), I(4), B(5), F(6), F(7)),
                "Cone" => Geometries.Cone(F(0), F(1), I(2), I(3), B(4), F(5), F(6)),
                "Sphere" => Geometries.Sphere(F(0), I(1), I(2), F(3), F(4), F(5), F(6)),
                "Torus" => Geometries.Torus(F(0), F(1), I(2), I(3), F(4)),
                _ => throw new InvalidOperationException(),
            };
        }

        static void Same(string what, JsonElement want, float[] got, string name)
        {
            var w = want.EnumerateArray().Select(e => e.GetDouble()).ToArray();
            Assert.True(got != null, $"{name}: {what} is null");
            Assert.True(w.Length == got.Length, $"{name}: {what} has {got.Length} values, three has {w.Length}");
            for (int i = 0; i < w.Length; i++)
                Assert.True(Math.Abs(w[i] - got[i]) <= 1e-5 + 1e-5 * Math.Abs(w[i]),
                    $"{name}: {what}[{i}] (vertex {i / (what == "uv" ? 2 : 3)}) is {got[i]}, three gives {w[i]}");
        }

        [Theory]
        [MemberData(nameof(Names))]
        public void MatchesThree(string name)
        {
            var c = Cases.Single(x => x.GetProperty("name").GetString() == name);
            var g = Build(c);
            Same("position", c.GetProperty("positions"), g.Positions, name);
            Same("normal", c.GetProperty("normals"), g.Normals, name);
            Same("uv", c.GetProperty("uvs"), g.Uvs, name);
            var wi = c.GetProperty("indices").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            Assert.True(g.Indices != null && g.Indices.Length == wi.Length, $"{name}: {g.Indices?.Length} indices, three has {wi.Length}");
            for (int i = 0; i < wi.Length; i++)
                Assert.True(wi[i] == g.Indices[i], $"{name}: index[{i}] (triangle {i / 3}) is {g.Indices[i]}, three gives {wi[i]}");
        }
    }
}
