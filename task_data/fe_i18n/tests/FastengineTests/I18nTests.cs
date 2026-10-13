using System.Text.Json;
using Fastengine;
using Xunit;

namespace FastengineTests
{
    // Fixtures are CarrierDominion's own client/i18n.js run under Node (js/make-fixtures.mjs) with the game's
    // catalogues; the Norwegian one has a few keys removed so that the English fallback shows.
    public class I18nTests
    {
        static readonly JsonElement Root = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures.json"))).RootElement;

        static Dictionary<string, string> Catalog(string lang)
        {
            var path = Path.Combine(AppContext.BaseDirectory, lang + ".json");
            var map = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(path));
            if (lang == "no") foreach (var k in Root.GetProperty("removedFromNo").EnumerateArray()) map.Remove(k.GetString());
            return map;
        }

        static object Value(JsonElement v) => v.ValueKind switch
        {
            JsonValueKind.Number => v.GetDouble(),
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            _ => v.GetString(),
        };

        static string S(JsonElement e) => e.ValueKind == JsonValueKind.Null ? null : e.GetString();

        [Fact]
        public void PickLang_MatchesTheBrowser()
        {
            var wrong = new List<string>();
            foreach (var p in Root.GetProperty("picks").EnumerateArray())
            {
                var got = I18n.PickLang(S(p.GetProperty("requested")), S(p.GetProperty("navigator")));
                if (got != p.GetProperty("lang").GetString())
                    wrong.Add($"({S(p.GetProperty("requested")) ?? "null"}, {S(p.GetProperty("navigator")) ?? "null"}) -> {got}, browser {p.GetProperty("lang")}");
            }
            Assert.True(wrong.Count == 0, string.Join("\n", wrong));
        }

        public static IEnumerable<object[]> Langs() => new[] { new object[] { "en" }, new object[] { "no" } };

        [Theory]
        [MemberData(nameof(Langs))]
        public void T_MatchesTheBrowser(string lang)
        {
            var en = Catalog("en");
            var t = new I18n(lang, lang == "en" ? en : Catalog("no"), en, _ => { });
            var wrong = new List<string>();
            foreach (var c in Root.GetProperty("translations").EnumerateArray().Where(c => c.GetProperty("lang").GetString() == lang))
            {
                var vars = c.GetProperty("vars").ValueKind == JsonValueKind.Null ? Array.Empty<(string, object)>()
                    : c.GetProperty("vars").EnumerateObject().Select(p => (p.Name, Value(p.Value))).ToArray();
                var got = t.T(c.GetProperty("key").GetString(), vars);
                if (got != c.GetProperty("text").GetString())
                    wrong.Add($"{c.GetProperty("key")} {c.GetProperty("vars")}: \"{got}\", browser \"{c.GetProperty("text")}\"");
            }
            Assert.True(wrong.Count == 0, string.Join("\n", wrong));
        }

        [Fact]
        public void MissingKeys_AreLoggedOnce()
        {
            var en = Catalog("en");
            var log = new List<string>();
            var t = new I18n("no", Catalog("no"), en, log.Add);
            for (int i = 0; i < 3; i++) { t.T("seat.team", ("team", 2)); t.T("no.such.key"); t.T("status.tooFar"); }
            Assert.Equal(new[] { "[I18n] missing no key seat.team", "[I18n] missing no key no.such.key" }, log);
        }

        [Theory]
        [InlineData("nb_NO.UTF-8", null, "en_US.UTF-8", "nb_NO.UTF-8")]
        [InlineData(null, "", "nn_NO.UTF-8", "nn_NO.UTF-8")]
        [InlineData("C", "POSIX", "de_DE.UTF-8", "de_DE.UTF-8")]
        [InlineData(null, "no_NO", "en_GB.UTF-8", "no_NO")]
        [InlineData(null, null, null, "")]
        [InlineData("C", null, "POSIX", "")]
        public void OsLanguage_FromTheEnvironment(string lcAll, string lcMessages, string lang, string expected)
        {
            var env = new Dictionary<string, string> { ["LC_ALL"] = lcAll, ["LC_MESSAGES"] = lcMessages, ["LANG"] = lang };
            Assert.Equal(expected, I18n.OsLanguage(name => env.GetValueOrDefault(name)));
        }

        [Fact]
        public void OsLanguage_NorwegianLinuxPicksNo()
        {
            var env = new Dictionary<string, string> { ["LANG"] = "nb_NO.UTF-8" };
            Assert.Equal("no", I18n.PickLang(null, I18n.OsLanguage(name => env.GetValueOrDefault(name))));
        }

        [Theory]
        [InlineData("ws://10.0.0.5:8080/play?code=AB12&token=x", "no", "http://10.0.0.5:8080/data/i18n/no.json")]
        [InlineData("wss://games.example.com/ws", "en", "https://games.example.com/data/i18n/en.json")]
        [InlineData("ws://box:80/", "en", "http://box/data/i18n/en.json")]
        [InlineData("wss://box:443/ws?spectate=1", "no", "https://box/data/i18n/no.json")]
        [InlineData("wss://box:8443/ws", "no", "https://box:8443/data/i18n/no.json")]
        public void CatalogUrl_OnTheServerPlayedOn(string socket, string lang, string expected) =>
            Assert.Equal(expected, I18n.CatalogUrl(socket, lang));
    }
}
