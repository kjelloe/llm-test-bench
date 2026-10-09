using System;
using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    // Keyboard input for the Unity client of boombrawl, meant to behave like js/input.js.
    // Update() runs once per frame; Unity calls OnApplicationFocus when the window gains or
    // loses focus.
    public sealed class DirectionInput
    {
        static readonly Dictionary<KeyCode, (int dx, int dy)> KeyMap = new Dictionary<KeyCode, (int, int)>
        {
            [KeyCode.W] = (0, -1), [KeyCode.UpArrow] = (0, -1),
            [KeyCode.S] = (0, 1), [KeyCode.DownArrow] = (0, 1),
            [KeyCode.A] = (-1, 0), [KeyCode.LeftArrow] = (-1, 0),
            [KeyCode.D] = (1, 0), [KeyCode.RightArrow] = (1, 0),
        };

        readonly Action<int, int> _onDir;
        readonly Action _onBomb, _onTrigger;
        readonly List<KeyCode> _held = new List<KeyCode>();
        int _dx, _dy;

        public DirectionInput(Action<int, int> onDir, Action onBomb, Action onTrigger)
        {
            _onDir = onDir;
            _onBomb = onBomb;
            _onTrigger = onTrigger;
        }

        public void Update()
        {
            if (Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.E)) _onBomb();
            if (Input.GetKeyDown(KeyCode.R)) _onTrigger();
            bool changed = false;
            foreach (KeyCode key in KeyMap.Keys)
            {
                if (Input.GetKeyDown(key))
                {
                    _held.Remove(key);
                    _held.Insert(0, key);
                    changed = true;
                }
                if (Input.GetKeyUp(key) && _held.Remove(key)) changed = true;
            }
            if (!changed) return;
            var (dx, dy) = _held.Count > 0 ? KeyMap[_held[0]] : (0, 0);
            Emit(dx, dy);
        }

        public void OnApplicationFocus(bool focused)
        {
            if (focused) return;
            _held.Clear();
            Emit(0, 0);
        }

        void Emit(int dx, int dy)
        {
            if (dx == _dx && dy == _dy) return;
            _dx = dx;
            _dy = dy;
            _onDir(dx, dy);
        }
    }
}
