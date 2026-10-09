using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // fixtures.json is produced by js/make-fixtures.mjs from the real library, called as the browser client
    // calls it. Each case is checked module for module: one wrong bit anywhere is a different code.
    public class QrCodeTests
    {
        sealed class Case { public string Text; public int Version; public string[] Modules; }

        static readonly JsonElement Root = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures.json"))).RootElement;

        static readonly Dictionary<string, Case> Cases = Root.GetProperty("cases").EnumerateArray()
            .Select(c => new Case
            {
                Text = c.GetProperty("text").GetString(),
                Version = c.GetProperty("version").GetInt32(),
                Modules = c.GetProperty("modules").EnumerateArray().Select(r => r.GetString()).ToArray(),
            })
            .GroupBy(c => c.Text).ToDictionary(g => g.Key, g => g.First());

        public static IEnumerable<object[]> ByVersion() =>
            Cases.Values.GroupBy(c => c.Version).OrderBy(g => g.Key).Select(g => new object[] { g.Key });

        static string Render(QrCode qr)
        {
            var sb = new StringBuilder();
            for (int r = 0; r < qr.ModuleCount; r++)
            {
                for (int c = 0; c < qr.ModuleCount; c++) sb.Append(qr.IsDark(r, c) ? '1' : '0');
                sb.Append('\n');
            }
            return sb.ToString();
        }

        [Fact]
        public void ChoosesTheSmallestVersionThatFits()
        {
            foreach (Case c in Cases.Values)
            {
                var qr = new QrCode(c.Text);
                Assert.True(qr.Version == c.Version, $"{c.Text.Length} bytes: version {qr.Version}, the browser uses {c.Version}");
                Assert.Equal(c.Version * 4 + 17, qr.ModuleCount);
            }
        }

        [Theory]
        [MemberData(nameof(ByVersion))]
        public void Matrix_MatchesTheBrowser_ModuleForModule(int version)
        {
            foreach (Case c in Cases.Values.Where(c => c.Version == version))
            {
                var qr = new QrCode(c.Text);
                Assert.Equal(c.Version, qr.Version);
                string expected = string.Join("\n", c.Modules) + "\n", actual = Render(qr);
                if (expected == actual) continue;
                int diff = Enumerable.Range(0, expected.Length).Count(i => i < actual.Length && expected[i] != actual[i]);
                Assert.True(false, $"\"{c.Text}\" ({c.Text.Length} bytes, version {version}): {diff} modules differ");
            }
        }

        [Fact]
        public void NonAsciiCharacters_KeepOnlyTheLowByte_AsTheBrowserDoes()
        {
            Case c = Cases.Values.Single(x => x.Text.Any(ch => ch > 127));
            Assert.Equal(string.Join("\n", c.Modules) + "\n", Render(new QrCode(c.Text)));
        }

        [Fact]
        public void TooLongForVersion10_Throws()
        {
            foreach (JsonElement t in Root.GetProperty("tooLong").EnumerateArray())
                Assert.Throws<ArgumentException>(() => new QrCode(t.GetString()));
        }
    }
}
