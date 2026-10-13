using System.Collections.Generic;

namespace Fastengine
{
    // The engine's log (stdout and a file in the real engine). Tests read it back.
    public static class Log
    {
        static readonly object Gate = new();
        static readonly List<string> Lines = new();

        public static void Line(string text)
        {
            lock (Gate) Lines.Add(text);
        }

        public static string[] Snapshot()
        {
            lock (Gate) return Lines.ToArray();
        }
    }
}
