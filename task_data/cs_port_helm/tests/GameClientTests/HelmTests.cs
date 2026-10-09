using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // fixtures.json comes from js/make-fixtures.mjs: 40 scripted sessions replayed through the real helm
    // code, with every message it sent and the helm state after each step.
    public class HelmTests
    {
        static readonly JsonElement Root = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures.json"))).RootElement;

        public static IEnumerable<object[]> Seeds() =>
            Root.GetProperty("sessions").EnumerateArray().Select(s => new object[] { s.GetProperty("seed").GetInt32() });

        static HelmView View(JsonElement v) => new HelmView
        {
            Team = v.GetProperty("team").GetInt32(),
            Carriers = v.GetProperty("carriers").EnumerateArray().Select(c => new CarrierView
            {
                Id = c.GetProperty("id").GetInt32(), Team = c.GetProperty("team").GetInt32(), Contact = c.GetProperty("contact").GetInt32(),
                Throttle = c.GetProperty("throttle").GetInt32(), Rudder = c.GetProperty("rudder").GetInt32(),
            }).ToList(),
            Units = v.GetProperty("units").EnumerateArray().Select(u => new UnitView
            {
                Id = u.GetProperty("id").GetInt32(), Team = u.GetProperty("team").GetInt32(),
                Kind = u.GetProperty("kind").GetInt32(), State = u.GetProperty("state").GetInt32(),
            }).ToList(),
        };

        static string Wire(Command c)
        {
            var parts = new List<string> { $"type={c.Type}" };
            void Add(string name, int? value) { if (value.HasValue) parts.Add($"{name}={value.Value}"); }
            Add("carrierId", c.CarrierId); Add("unitId", c.UnitId); Add("throttle", c.Throttle);
            Add("rudder", c.Rudder); Add("climb", c.Climb); Add("kind", c.Kind);
            return string.Join(" ", parts.OrderBy(p => p, StringComparer.Ordinal));
        }

        static string Wire(JsonElement m) => string.Join(" ",
            m.EnumerateObject().Select(p => p.Name + "=" + (p.Value.ValueKind == JsonValueKind.String ? p.Value.GetString() : p.Value.GetRawText()))
                .OrderBy(p => p, StringComparer.Ordinal));

        static string Step(JsonElement op)
        {
            string name = op.GetProperty("op").GetString();
            return op.TryGetProperty("value", out JsonElement v) ? $"{name} {v.GetInt32()}" : op.TryGetProperty("kind", out JsonElement k) ? $"{name} {k.GetInt32()}" : name;
        }

        [Theory]
        [MemberData(nameof(Seeds))]
        public void Session_SendsWhatTheBrowserSends(int seed)
        {
            JsonElement session = Root.GetProperty("sessions").EnumerateArray().Single(s => s.GetProperty("seed").GetInt32() == seed);
            var sent = new List<Command>();
            var helm = new Helm(sent.Add);
            int i = 0;
            foreach (JsonElement step in session.GetProperty("steps").EnumerateArray())
            {
                JsonElement op = step.GetProperty("op");
                switch (op.GetProperty("op").GetString())
                {
                    case "view": helm.OnSnapshot(View(op.GetProperty("view"))); break;
                    case "w": helm.ThrottleUp(); break;
                    case "s": helm.ThrottleDown(); break;
                    case "x": helm.Stop(); break;
                    case "rudder": helm.SendRudder(op.GetProperty("value").GetInt32()); break;
                    case "climb": helm.SendClimb(op.GetProperty("value").GetInt32()); break;
                    case "cycle": helm.CycleSelection(); break;
                    case "launch": helm.Launch(op.GetProperty("kind").GetInt32()); break;
                    case "pilot": helm.TogglePiloting(); break;
                    case "escort": helm.OrderEscort(); break;
                    case "recall": helm.RecallSelected(); break;
                }
                string where = $"seed {seed}, step {i} ({Step(op)})";
                Assert.Equal(step.GetProperty("sent").EnumerateArray().Select(Wire).ToList(), sent.Select(Wire).ToList());
                JsonElement st = step.GetProperty("state");
                string expected = $"throttle={st.GetProperty("throttle").GetInt32()} rudder={st.GetProperty("rudder").GetInt32()} climb={st.GetProperty("climb").GetInt32()} " +
                                  $"selected={st.GetProperty("selectedUnitId").GetInt32()} piloting={st.GetProperty("piloting").GetBoolean()} carrier={st.GetProperty("carrierId").GetInt32()}";
                string actual = $"throttle={helm.Throttle} rudder={helm.Rudder} climb={helm.Climb} selected={helm.SelectedUnitId} piloting={helm.Piloting} carrier={helm.CarrierId}";
                Assert.True(expected == actual, $"{where}: expected {expected}, got {actual}");
                sent.Clear();
                i++;
            }
        }

        [Fact]
        public void BeforeAnyView_NothingIsSent()
        {
            var sent = new List<Command>();
            var helm = new Helm(sent.Add);
            helm.ThrottleUp(); helm.SendRudder(1); helm.Launch(0); helm.TogglePiloting(); helm.SendClimb(1);
            Assert.Empty(sent);
            Assert.Equal(-1, helm.CarrierId);
        }
    }
}
