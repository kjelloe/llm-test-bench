using System;
using System.Collections.Generic;
using UnityEngine;

namespace GameClient
{
    /// <summary>
    /// Local-player prediction: sends one sequenced input per client tick, simulates it
    /// immediately with the shared Movement integrator, and on each authoritative snapshot
    /// rewinds to the server position and replays the inputs the server has not applied yet.
    /// </summary>
    public sealed class Predictor
    {
        readonly Func<int, int, bool> _blocked;
        readonly Action<InputCommand> _send;
        readonly List<InputCommand> _pending = new List<InputCommand>();
        int _localId = -1;
        int _dirX, _dirY;
        int _seq;
        int _speed = Movement.SpeedBase;

        public Predictor(Func<int, int, bool> blocked, Action<InputCommand> send)
        {
            _blocked = blocked;
            _send = send;
        }

        public int X { get; private set; }
        public int Y { get; private set; }
        public bool Active { get; private set; }
        public int PendingCount => _pending.Count;

        public Vector3 RenderPosition => new Vector3(X / Movement.Cell, 0f, Y / Movement.Cell);

        public void SetLocalPlayer(int id) => _localId = id;

        public void SetDirection(int dx, int dy)
        {
            _dirX = dx;
            _dirY = dy;
        }

        public void Tick()
        {
            _seq++;
            var input = new InputCommand { Seq = _seq, Dx = _dirX, Dy = _dirY };
            _send(input);
            Apply(input);
            _pending.Add(input);
        }

        public void OnSnapshot(AuthoritativeSnapshot snap)
        {
            PlayerSnapshot me = snap.Players.Find(p => p.Id == _localId);
            if (me == null)
            {
                Active = false;
                return;
            }

            if (snap.Phase == "play" && me.Status == "alive")
            {
                Active = true;
                _pending.RemoveAll(i => i.Seq < me.Seq);
                foreach (InputCommand i in _pending) Apply(i);
                X = me.X;
                Y = me.Y;
            }
            else
            {
                Active = false;
                X = me.X;
                Y = me.Y;
            }
            _speed = Movement.SpeedForLevel(me.SpeedLevel);
        }

        void Apply(InputCommand input)
        {
            (int x, int y) = Movement.Step(X, Y, input.Dx, input.Dy, _speed, _blocked);
            X = x;
            Y = y;
        }
    }
}
