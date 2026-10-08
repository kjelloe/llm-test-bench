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
        int _lastTick = int.MinValue;

        public Predictor(Func<int, int, bool> blocked, Action<InputCommand> send)
        {
            _blocked = blocked ?? throw new ArgumentNullException(nameof(blocked));
            _send = send ?? throw new ArgumentNullException(nameof(send));
        }

        public int X { get; private set; }
        public int Y { get; private set; }
        public bool Active { get; private set; }
        public int PendingCount => _pending.Count;

        public Vector3 RenderPosition => new Vector3(X / (float)Movement.Cell, 0f, Y / (float)Movement.Cell);

        public void SetLocalPlayer(int id) => _localId = id;

        public void SetDirection(int dx, int dy)
        {
            if (dx < -1 || dx > 1) throw new ArgumentOutOfRangeException(nameof(dx));
            if (dy < -1 || dy > 1) throw new ArgumentOutOfRangeException(nameof(dy));
            if (dx != 0) dy = 0;
            _dirX = dx;
            _dirY = dy;
        }

        public void Tick()
        {
            _seq++;
            var input = new InputCommand { Seq = _seq, Dx = _dirX, Dy = _dirY };
            _send(input);
            if (!Active) return;
            Apply(input);
            _pending.Add(input);
        }

        public void OnSnapshot(AuthoritativeSnapshot snap)
        {
            if (snap == null) throw new ArgumentNullException(nameof(snap));
            if (snap.Tick <= _lastTick) return;
            _lastTick = snap.Tick;

            PlayerSnapshot me = snap.Players.Find(p => p.Id == _localId);
            if (me == null)
            {
                Active = false;
                _pending.Clear();
                return;
            }

            _speed = Movement.SpeedForLevel(me.SpeedLevel);
            X = me.X;
            Y = me.Y;
            if (snap.Phase == "play" && me.Status == "alive")
            {
                Active = true;
                _pending.RemoveAll(i => i.Seq <= me.Seq);
                foreach (InputCommand i in _pending) Apply(i);
            }
            else
            {
                Active = false;
                _pending.Clear();
            }
        }

        void Apply(InputCommand input)
        {
            (int x, int y) = Movement.Step(X, Y, input.Dx, input.Dy, _speed, _blocked);
            X = x;
            Y = y;
        }
    }
}
