using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    // Draws a name label over every unit. It is added to the same GameObject as the GameRoot.
    // Runs after CameraRig (100), so labels use the camera position of this frame.
    [DefaultExecutionOrder(200)]
    public sealed class Hud : MonoBehaviour
    {
        public CameraRig rig;

        // The canvas the labels live under; created in Start.
        public Transform canvas;

        readonly Dictionary<Unit, GameObject> _labels = new Dictionary<Unit, GameObject>();

        public int LabelCount => _labels.Count;

        // At the scene root: GameRoot.NewGame destroys everything under the root.
        void Start() => canvas = new GameObject("HudCanvas").transform;

        // Called by the game for every unit it spawns.
        public void Track(Unit unit)
        {
            var label = new GameObject("Label:" + unit.id);
            label.transform.SetParent(canvas, false);
            _labels[unit] = label;
        }

        public GameObject LabelFor(Unit unit) => _labels.TryGetValue(unit, out var label) ? label : null;

        void LateUpdate()
        {
            List<Unit> gone = null;
            foreach (var pair in _labels)
            {
                if (pair.Key == null)   // Unity's == sees a destroyed unit; `is null` and `?.` do not
                {
                    (gone ??= new List<Unit>()).Add(pair.Key);
                    continue;
                }
                Vector2 screen = rig.WorldToScreen(pair.Key.transform.position);
                pair.Value.transform.localPosition = new Vector3(screen.x, screen.y, 0f);
            }
            if (gone == null) return;
            foreach (var unit in gone)
            {
                Destroy(_labels[unit]);
                _labels.Remove(unit);
            }
        }
    }
}
