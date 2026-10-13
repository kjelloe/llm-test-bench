using System.Text.Json;
using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Fixtures are Chromium's own layout of each case (tools/make_fixtures.reference.mjs, Playwright).
    public class FlexLayoutTests
    {
        static readonly JsonElement[] Cases = JsonDocument.Parse(File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "fixtures.json"))).RootElement.EnumerateArray().ToArray();

        public static IEnumerable<object[]> Names() => Cases.Select(c => new object[] { c.GetProperty("name").GetString() });

        static Justify J(string s) => s switch { "center" => Justify.Center, "space-between" => Justify.SpaceBetween, "flex-end" => Justify.FlexEnd, _ => Justify.FlexStart };
        static Align A(string s) => s switch { "center" => Align.Center, "flex-end" => Align.FlexEnd, _ => Align.FlexStart };

        [Theory]
        [MemberData(nameof(Names))]
        public void MatchesChromium(string name)
        {
            var c = Cases.Single(x => x.GetProperty("name").GetString() == name);
            var items = c.GetProperty("items").EnumerateArray()
                .Select(i => new Box((float)i[0].GetDouble(), (float)i[1].GetDouble())).ToList();
            var got = FlexLayout.WrapRow((float)c.GetProperty("width").GetDouble(), (float)c.GetProperty("rowGap").GetDouble(),
                (float)c.GetProperty("columnGap").GetDouble(), J(c.GetProperty("justify").GetString()),
                A(c.GetProperty("align").GetString()), items);
            var want = c.GetProperty("positions").EnumerateArray().ToArray();
            Assert.Equal(want.Length, got.Length);
            for (int i = 0; i < want.Length; i++)
            {
                double wx = want[i][0].GetDouble(), wy = want[i][1].GetDouble();
                Assert.True(Math.Abs(wx - got[i].X) < 0.05 && Math.Abs(wy - got[i].Y) < 0.05,
                    $"{name}: item {i} at ({got[i].X}, {got[i].Y}), Chromium puts it at ({wx}, {wy})");
            }
        }
    }
}
