using System;
using System.Collections.Generic;
using System.Threading;
using UnityEngine;

namespace GameClient
{
    /// <summary>
    /// Network callbacks arrive on worker threads, but Unity objects may only be
    /// touched on the main thread. Workers Enqueue work; the main loop calls
    /// Drain() once per frame.
    /// </summary>
    public sealed class MainThreadDispatcher
    {
        private readonly Queue<Action> _queue = new Queue<Action>();
        private readonly object _gate = new object();
        private int _mainThreadId = -1;
        private long _dropped;
        private long _exceptions;

        public MainThreadDispatcher(int capacity, int maxPerFrame)
        {
            if (capacity < 1) throw new ArgumentOutOfRangeException(nameof(capacity));
            if (maxPerFrame < 1) throw new ArgumentOutOfRangeException(nameof(maxPerFrame));
            Capacity = capacity;
            MaxPerFrame = maxPerFrame;
        }

        public int Capacity { get; }
        public int MaxPerFrame { get; }
        public long DroppedCount => Interlocked.Read(ref _dropped);
        public long ExceptionCount => Interlocked.Read(ref _exceptions);

        public int Pending
        {
            get { lock (_gate) return _queue.Count; }
        }

        public bool Enqueue(Action action)
        {
            if (action == null) throw new ArgumentNullException(nameof(action));
            lock (_gate)
            {
                if (_queue.Count >= Capacity)
                {
                    _dropped++;
                    return false;
                }
                _queue.Enqueue(action);
                return true;
            }
        }

        public int Drain()
        {
            int current = Environment.CurrentManagedThreadId;
            int bound = Interlocked.CompareExchange(ref _mainThreadId, current, -1);
            if (bound != -1 && bound != current)
                throw new InvalidOperationException("Drain must be called from the main thread");

            int budget;
            lock (_gate) budget = Math.Min(_queue.Count, MaxPerFrame);

            for (int i = 0; i < budget; i++)
            {
                Action action;
                lock (_gate) action = _queue.Dequeue();
                try
                {
                    action();
                }
                catch (Exception e)
                {
                    Interlocked.Increment(ref _exceptions);
                    Debug.LogException(e);
                }
            }
            return budget;
        }
    }
}
