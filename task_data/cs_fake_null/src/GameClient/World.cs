// The game's own scripts. Do not edit; the HUD in Hud.cs works with them.
using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    // A unit moves by its velocity once per frame.
    public sealed class Unit : MonoBehaviour
    {
        public int id;
        public Vector3 velocity;

        void Update() => transform.position += velocity;
    }

    // Follows its target after the units have moved.
    [DefaultExecutionOrder(100)]
    public sealed class CameraRig : MonoBehaviour
    {
        public Unit target;
        public Vector3 offset = new Vector3(0f, 10f, -10f);

        void LateUpdate()
        {
            if (target) transform.position = target.transform.position + offset;
        }

        // Screen position (pixels, 800x600 view) of a world point for the camera's current position.
        public Vector2 WorldToScreen(Vector3 world)
        {
            Vector3 d = world - transform.position;
            return new Vector2(400f + 10f * d.x, 300f + 10f * (d.z - offset.z));
        }
    }

    // Owns the units. Every unit is a child of the root's GameObject.
    public sealed class GameRoot : MonoBehaviour
    {
        public Unit Spawn(int id, Vector3 position, Vector3 velocity)
        {
            var go = new GameObject("Unit:" + id);
            go.transform.SetParent(transform, false);
            go.transform.position = position;
            var unit = go.AddComponent<Unit>();
            unit.id = id;
            unit.velocity = velocity;
            return unit;
        }

        // Starts a new game: everything under the root is destroyed (at the end of this frame).
        public void NewGame()
        {
            for (int i = 0; i < transform.childCount; i++)
                Destroy(transform.GetChild(i).gameObject);
        }
    }
}
