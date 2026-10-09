using System;
using UnityEngine;

namespace GameClient
{
    // Keyboard input for the Unity client of boombrawl, meant to behave like js/input.js.
    // Update() runs once per frame; Unity calls OnApplicationFocus when the window gains or
    // loses focus.
    public sealed class DirectionInput
    {
        readonly Action<int, int> _onDir;
        readonly Action _onBomb, _onTrigger;
        int _dx, _dy;

        public DirectionInput(Action<int, int> onDir, Action onBomb, Action onTrigger)
        {
            _onDir = onDir;
            _onBomb = onBomb;
            _onTrigger = onTrigger;
        }

        public void Update()
        {
            if (Input.GetKeyDown(KeyCode.Space)) _onBomb();
            int dx = 0, dy = 0;
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) dy = -1;
            else if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) dy = 1;
            else if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) dx = -1;
            else if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) dx = 1;
            if (dx == _dx && dy == _dy) return;
            _dx = dx;
            _dy = dy;
            _onDir(dx, dy);
        }

        public void OnApplicationFocus(bool focused) { }
    }
}
