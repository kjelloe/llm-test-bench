using System.Numerics;
using System.Text.Json;
using Fastengine.Three;
using Xunit;

namespace FastengineTests
{
    // Fixtures are three r162's own matrixWorld after the lookAt calls (js/make-fixtures.reference.mjs).
    public class Object3DTests
    {
        static readonly JsonElement[] Cases = Load();

        static JsonElement[] Load()
        {
            var path = Path.Combine(AppContext.BaseDirectory, "fixtures.json");
            return JsonDocument.Parse(File.ReadAllText(path)).RootElement.EnumerateArray().ToArray();
        }

        public static IEnumerable<object[]> Names() => Cases.Select(c => new object[] { c.GetProperty("name").GetString() });

        static Vector3 V(JsonElement e)
        {
            var a = e.EnumerateArray().Select(x => (float)x.GetDouble()).ToArray();
            return new Vector3(a[0], a[1], a[2]);
        }

        static Object3D Build(JsonElement e, Dictionary<int, Object3D> byId)
        {
            Object3D o = e.GetProperty("kind").GetString() == "camera" ? new Camera() : new Object3D();
            o.Position = V(e.GetProperty("position"));
            o.Rotation = V(e.GetProperty("rotation"));
            o.Scale = V(e.GetProperty("scale"));
            byId[e.GetProperty("id").GetInt32()] = o;
            foreach (var child in e.GetProperty("children").EnumerateArray()) o.Add(Build(child, byId));
            return o;
        }

        static float[] Elements(Matrix4x4 m) => new[]
        {
            m.M11, m.M12, m.M13, m.M14, m.M21, m.M22, m.M23, m.M24, m.M31, m.M32, m.M33, m.M34, m.M41, m.M42, m.M43, m.M44,
        };

        [Theory]
        [MemberData(nameof(Names))]
        public void MatchesThree(string name)
        {
            var c = Cases.Single(x => x.GetProperty("name").GetString() == name);
            var byId = new Dictionary<int, Object3D>();
            Build(c.GetProperty("tree"), byId);
            foreach (var look in c.GetProperty("looks").EnumerateArray())
                byId[look.GetProperty("id").GetInt32()].LookAt(V(look.GetProperty("target")));
            foreach (var entry in c.GetProperty("world").EnumerateObject())
            {
                var want = entry.Value.EnumerateArray().Select(x => x.GetDouble()).ToArray();
                var got = Elements(byId[int.Parse(entry.Name)].WorldMatrix);
                for (int i = 0; i < 16; i++)
                    Assert.True(Math.Abs(want[i] - got[i]) <= 1e-4 + 1e-4 * Math.Abs(want[i]),
                        $"{name}: node {entry.Name} world element {i} is {got[i]}, three gives {want[i]}");
            }
        }
    }
}
