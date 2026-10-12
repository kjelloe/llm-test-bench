using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Fastengine
{
    // Adapted from fastengine's SoloServer.cs.
    public sealed class SoloServer : IDisposable
    {
        readonly string _dir, _node;
        readonly ConcurrentQueue<Action> _main = new();
        Process _process;

        public SoloServer(string soloDir, string nodePath = "node") { _dir = soloDir; _node = nodePath; }

        public event Action<string> Ready;
        public event Action<string> Failed;

        public int? Pid => _process?.Id;

        public void Start(string stateDir, IReadOnlyDictionary<string, string> launchEnv = null)
        {
            using var spec = JsonDocument.Parse(File.ReadAllText(Path.Combine(_dir, "solo.json")));
            var root = spec.RootElement;
            var ready = new Regex(root.GetProperty("ready").GetString());
            var wsPath = root.GetProperty("ws").GetString();
            var info = new ProcessStartInfo(_node)
            {
                WorkingDirectory = Path.Combine(_dir, "game"),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardInput = true,   // held open: the guard stops the server when it closes
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            info.ArgumentList.Add("-r");
            info.ArgumentList.Add(Path.Combine(_dir, "guard.cjs"));
            info.ArgumentList.Add(root.GetProperty("entry").GetString());
            foreach (var p in root.GetProperty("env").EnumerateObject())
                info.Environment[p.Name] = p.Value.GetString().Replace("{state}", stateDir);
            if (launchEnv != null)
                foreach (var (key, value) in launchEnv) info.Environment[key] = value.Replace("{state}", stateDir);
            var port = FreePort();
            info.Environment["HOST"] = "127.0.0.1";
            info.Environment["PORT"] = port.ToString();
            info.Environment["STATE_DIR"] = stateDir;
            Directory.CreateDirectory(stateDir);

            var announced = false;
            var process = _process = new Process { StartInfo = info, EnableRaisingEvents = true };
            process.OutputDataReceived += (_, e) =>
            {
                if (e.Data == null) return;
                Log.Line("[Server] " + e.Data);
                if (announced || !ready.IsMatch(e.Data)) return;
                announced = true;
                var url = $"ws://127.0.0.1:{port}{wsPath}";
                _main.Enqueue(() => Ready?.Invoke(url));
            };
            process.ErrorDataReceived += (_, e) => { if (e.Data != null) Log.Line("[Server] " + e.Data); };
            process.Exited += (_, _) =>
            {
                if (_process != process) return;   // stopped by Dispose: not a failure
                var code = process.ExitCode;
                _main.Enqueue(() => Failed?.Invoke($"single player stopped (exit {code})"));
            };
            try { process.Start(); }
            catch (Exception e) when (e is System.ComponentModel.Win32Exception || e is IOException)
            {
                _process = null;
                _main.Enqueue(() => Failed?.Invoke("single player cannot start: " + e.Message));
                return;
            }
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
        }

        static int FreePort()
        {
            var l = new TcpListener(IPAddress.Loopback, 0);
            l.Start();
            var port = ((IPEndPoint)l.LocalEndpoint).Port;
            l.Stop();
            return port;
        }

        public void Pump()
        {
            while (_main.TryDequeue(out var a)) a();
        }

        // Close stdin first: the guard raises SIGTERM, so the server saves; then kill anything still running.
        public void Dispose()
        {
            var process = _process;
            if (process == null) return;
            _process = null;
            try
            {
                process.StandardInput.Close();
                if (!process.WaitForExit(2500)) process.Kill(entireProcessTree: true);
                process.WaitForExit();
            }
            catch (Exception e) when (e is InvalidOperationException || e is IOException) { }
        }
    }
}
