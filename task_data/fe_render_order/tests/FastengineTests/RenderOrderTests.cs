using System.Text.Json;
using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Fixtures are three r162's own result (js/make-fixtures.reference.mjs projects and sorts each scene the way
    // WebGLRenderer.projectObject and WebGLRenderList do, with three's sort functions).
    public class RenderOrderTests
    {
        static readonly JsonElement[] Cases = Load();

        static JsonElement[] Load()
        {
            var path = Path.Combine(AppContext.BaseDirectory, "fixtures.json");
            return JsonDocument.Parse(File.ReadAllText(path)).RootElement.EnumerateArray().ToArray();
        }

        public static IEnumerable<object[]> Names() => Cases.Select(c => new object[] { c.GetProperty("name").GetString() });

        static double[] Numbers(JsonElement e) => e.EnumerateArray().Select(x => x.GetDouble()).ToArray();

        static RenderMaterial Material(JsonElement m) => new()
        {
            Id = m.GetProperty("id").GetInt32(),
            Transparent = m.GetProperty("transparent").GetBoolean(),
            Transmission = m.GetProperty("transmission").GetDouble(),
            Visible = m.GetProperty("visible").GetBoolean(),
        };

        static SceneNode Node(JsonElement e)
        {
            var n = new SceneNode
            {
                Id = e.GetProperty("id").GetInt32(),
                Kind = e.GetProperty("kind").GetString(),
                RenderOrder = e.GetProperty("renderOrder").GetInt32(),
                Visible = e.GetProperty("visible").GetBoolean(),
                World = Numbers(e.GetProperty("world")),
            };
            if (e.TryGetProperty("center", out var c)) n.Center = Numbers(c);
            if (e.TryGetProperty("material", out var m)) n.Material = Material(m);
            if (e.TryGetProperty("materials", out var ms))
            {
                n.Materials = ms.EnumerateArray().Select(Material).ToList();
                n.GroupMaterials = e.GetProperty("groupMaterials").EnumerateArray().Select(x => x.GetInt32()).ToList();
            }
            foreach (var child in e.GetProperty("children").EnumerateArray()) n.Children.Add(Node(child));
            return n;
        }

        static void Same(string list, JsonElement want, List<int> got, string name)
        {
            var w = want.EnumerateArray().Select(x => x.GetInt32()).ToList();
            Assert.True(got != null, $"{name}: {list} is null");
            Assert.True(w.SequenceEqual(got), $"{name}: {list} is [{string.Join(", ", got)}], three draws [{string.Join(", ", w)}]");
        }

        [Theory]
        [MemberData(nameof(Names))]
        public void MatchesThree(string name)
        {
            var c = Cases.Single(x => x.GetProperty("name").GetString() == name);
            var lists = RenderOrder.Build(Node(c.GetProperty("scene")), Numbers(c.GetProperty("viewProjection")),
                Numbers(c.GetProperty("cameraPosition")));
            Same("opaque", c.GetProperty("opaque"), lists.Opaque, name);
            Same("transmissive", c.GetProperty("transmissive"), lists.Transmissive, name);
            Same("transparent", c.GetProperty("transparent"), lists.Transparent, name);
        }
    }
}
