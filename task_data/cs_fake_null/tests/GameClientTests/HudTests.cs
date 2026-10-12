using System.Linq;
using GameClient;
using UnityEngine;
using Xunit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace GameClientTests
{
    // PlayerLoop is static, so every test builds its own scene from a reset loop.
    public class HudTests
    {
        readonly GameRoot _root;
        readonly Hud _hud;
        readonly CameraRig _rig;
        readonly int _logStart;

        public HudTests()
        {
            PlayerLoop.Reset();
            _rig = new GameObject("Camera").AddComponent<CameraRig>();
            var game = new GameObject("Game");
            _root = game.AddComponent<GameRoot>();
            _hud = game.AddComponent<Hud>();
            _hud.rig = _rig;
            PlayerLoop.Step();   // Start
            _logStart = UnityEngine.Debug.Snapshot().Length;
        }

        string[] NewExceptions() =>
            UnityEngine.Debug.Snapshot().Skip(_logStart).Where(l => l.StartsWith("EXCEPTION")).ToArray();

        Unit SpawnTracked(int id, Vector3 position, Vector3 velocity)
        {
            var unit = _root.Spawn(id, position, velocity);
            _hud.Track(unit);
            return unit;
        }

        void AssertLabelOver(Unit unit)
        {
            var label = _hud.LabelFor(unit);
            Assert.True(label != null, $"no live label for unit {unit.id}");
            Vector2 s = _rig.WorldToScreen(unit.transform.position);
            Vector3 want = new Vector3(s.x, s.y, 0f), got = label.transform.localPosition;
            Assert.True(got == want, $"frame {PlayerLoop.frameCount}: label {unit.id} at {got}, unit is at {want} on screen this frame");
        }

        [Fact]
        public void Labels_UseThisFramesUnitAndCameraPositions()
        {
            var a = SpawnTracked(1, Vector3.zero, new Vector3(1f, 0f, 0f));
            var b = SpawnTracked(2, new Vector3(5f, 0f, 5f), new Vector3(0f, 0f, -1f));
            _rig.target = a;
            for (int frame = 0; frame < 3; frame++)
            {
                PlayerLoop.Step();
                AssertLabelOver(a);
                AssertLabelOver(b);
            }
            Assert.Empty(NewExceptions());
        }

        [Fact]
        public void Labels_AreNamedAfterTheirUnit_UnderTheCanvas()
        {
            var unit = SpawnTracked(7, Vector3.zero, Vector3.zero);
            PlayerLoop.Step();
            var label = _hud.LabelFor(unit);
            Assert.Equal("Label:7", label.name);
            Assert.Same(_hud.canvas, label.transform.parent);
        }

        [Fact]
        public void TheCanvas_SurvivesANewGame_AndNewUnitsGetLabels()
        {
            SpawnTracked(1, Vector3.zero, Vector3.zero);
            PlayerLoop.Step();
            _root.NewGame();
            PlayerLoop.Step();
            Assert.True(_hud.canvas.gameObject != null, "the canvas was destroyed by GameRoot.NewGame");
            for (var t = _hud.canvas; t != null; t = t.parent)
                Assert.NotSame(_root.transform, t);
            var fresh = SpawnTracked(2, new Vector3(3f, 0f, 0f), Vector3.zero);
            _rig.target = fresh;
            PlayerLoop.Step();
            AssertLabelOver(fresh);
            Assert.True(_hud.LabelFor(fresh).transform.parent.gameObject != null, "label hangs under a destroyed canvas");
            Assert.Empty(NewExceptions());
        }

        [Fact]
        public void ADestroyedUnit_LosesItsLabel_WithoutErrors()
        {
            var doomed = SpawnTracked(1, Vector3.zero, new Vector3(1f, 0f, 0f));
            var kept = SpawnTracked(2, new Vector3(4f, 0f, 0f), Vector3.zero);
            PlayerLoop.Step();
            var label = _hud.LabelFor(doomed);
            UnityEngine.Object.Destroy(doomed.gameObject);
            PlayerLoop.Step();   // the unit goes away at the end of this frame
            PlayerLoop.Step();   // the HUD notices and removes its label
            PlayerLoop.Step();
            Assert.True(label == null, "the dead unit's label is still alive");
            Assert.Equal(1, _hud.LabelCount);
            AssertLabelOver(kept);
            Assert.Empty(NewExceptions());
        }

        [Fact]
        public void SeveralUnitsDestroyedInOneFrame_AreAllCleanedUp()
        {
            var units = Enumerable.Range(1, 5).Select(i => SpawnTracked(i, new Vector3(i, 0f, 0f), Vector3.zero)).ToArray();
            PlayerLoop.Step();
            foreach (var u in units.Take(3)) UnityEngine.Object.Destroy(u.gameObject);
            for (int i = 0; i < 3; i++) PlayerLoop.Step();
            Assert.Equal(2, _hud.LabelCount);
            Assert.Equal(2, _hud.canvas.childCount);
            foreach (var u in units.Skip(3)) AssertLabelOver(u);
            Assert.Empty(NewExceptions());
        }

        [Fact]
        public void ANewGame_RemovesEveryLabel()
        {
            for (int i = 1; i <= 3; i++) SpawnTracked(i, new Vector3(i, 0f, i), Vector3.zero);
            PlayerLoop.Step();
            _root.NewGame();
            for (int i = 0; i < 3; i++) PlayerLoop.Step();
            Assert.Equal(0, _hud.LabelCount);
            Assert.True(_hud.canvas.gameObject != null, "the canvas was destroyed by GameRoot.NewGame");
            Assert.Equal(0, _hud.canvas.childCount);
            Assert.Empty(NewExceptions());
        }
    }
}
