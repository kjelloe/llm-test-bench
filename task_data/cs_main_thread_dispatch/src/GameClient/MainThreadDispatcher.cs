using System;
using System.Collections.Generic;
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
        private readonly List<Action> _queue = new List<Action>();

        public MainThreadDispatcher(int capacity, int maxPerFrame)
        {
            Capacity = capacity;
            MaxPerFrame = maxPerFrame;
        }

        public int Capacity { get; }
        public int MaxPerFrame { get; }
        public long DroppedCount { get; private set; }
        public long ExceptionCount { get; private set; }

        public int Pending => _queue.Count;

        public bool Enqueue(Action action)
        {
            _queue.Add(action);
            return true;
        }

        public int Drain()
        {
            int ran = 0;
            lock (_queue)
            {
                while (_queue.Count > 0)
                {
                    Action action = _queue[0];
                    _queue.RemoveAt(0);
                    action();
                    ran++;
                }
            }
            return ran;
        }
    }
}
