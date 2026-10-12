using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    // Draws a name label over every unit. It is added to the same GameObject as the GameRoot.
    public sealed class Hud : MonoBehaviour
    {
        public CameraRig rig;

        // The canvas the labels live under; created in Start.
        public Transform canvas;

        readonly Dictionary<Unit, GameObject> _labels = new Dictionary<Unit, GameObject>();

        public int LabelCount => _labels.Count;

        void Start()
        {
            canvas = new GameObject("HudCanvas").transform;
            canvas.SetParent(transform, false);
        }

        // Called by the game for every unit it spawns.
        public void Track(Unit unit)
        {
            var label = new GameObject("Label:" + unit.id);
            label.transform.SetParent(canvas, false);
            _labels[unit] = label;
        }

        public GameObject LabelFor(Unit unit) => _labels.TryGetValue(unit, out var label) ? label : null;

        void Update()
        {
            foreach (var pair in _labels)
            {
                if (pair.Key is null)
                {
                    Destroy(pair.Value);
                    _labels.Remove(pair.Key);
                    continue;
                }
                Vector2 screen = rig.WorldToScreen(pair.Key?.transform.position ?? Vector3.zero);
                pair.Value.transform.localPosition = new Vector3(screen.x, screen.y, 0f);
            }
        }
    }
}
