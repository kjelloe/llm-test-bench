"""strata-run.sh against stand-in Strata servers: it starts the engine, waits until it serves, hands run.sh the
openai-ext arguments with the right label, and stops the server on exit."""
import os
import shutil
import socket
import stat
import subprocess
import sys
import textwrap
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

REPO = Path(__file__).resolve().parent.parent

STAND_IN_SERVER = textwrap.dedent("""\
    import json, os, sys
    from http.server import BaseHTTPRequestHandler, HTTPServer
    port = int(sys.argv[sys.argv.index("--port") + 1])
    open(os.environ["STAND_IN_PIDFILE"], "w").write(str(os.getpid()))
    if os.environ.get("STAND_IN_CRASH"):
        print("engine failed to load", flush=True)
        sys.exit(3)
    open(os.environ["STAND_IN_ENV"], "w").write(os.environ.get("LD_LIBRARY_PATH", ""))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = {"/health": {"loaded": True}, "/v1/health": {"status": "ok"},
                    "/v1/models": {"data": [{"id": "stand-in"}]}}.get(self.path)
            self.send_response(200 if body else 404)
            self.end_headers()
            self.wfile.write(json.dumps(body or {}).encode())
        def log_message(self, *a):
            pass
    HTTPServer(("127.0.0.1", port), H).serve_forever()
""")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def rig(tmp_path):
    """A copy of strata-run.sh beside a stand-in run.sh, plus Niko- and ro99-style engine dirs."""
    bench = tmp_path / "bench"
    bench.mkdir()
    shutil.copy(REPO / "strata-run.sh", bench / "strata-run.sh")
    _executable(bench / "run.sh", f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{tmp_path}/run-args"\n')
    (tmp_path / "server.py").write_text(STAND_IN_SERVER)
    launcher = f'#!/usr/bin/env bash\nexec "{sys.executable}" "{tmp_path}/server.py" "$@"\n'
    _executable(tmp_path / "niko" / ".venv" / "bin" / "python", launcher)
    _executable(tmp_path / "ro99" / "build" / "strata-server", launcher)
    config = tmp_path / "cfg" / "my-model.json"
    config.parent.mkdir()
    config.write_text("{}")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "STRATA_PORT": str(_free_port()),
           "STRATA_DIR": str(tmp_path / "niko"), "STRATA_RO99_DIR": str(tmp_path / "ro99"),
           "STRATA_LOAD_TIMEOUT": "60", "STAND_IN_PIDFILE": str(tmp_path / "pid"),
           "STAND_IN_ENV": str(tmp_path / "server-env")}
    return tmp_path, bench, config, env


def _run(bench: Path, args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(bench / "strata-run.sh"), *args], env=env, capture_output=True,
                          text=True, timeout=120)


def _server_gone(tmp: Path) -> bool:
    pid = int((tmp / "pid").read_text())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return Path(f"/proc/{pid}/stat").exists() and Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"


def test_niko_mode_hands_run_sh_the_endpoint_and_label_then_stops_the_server(rig):
    tmp, bench, config, env = rig
    proc = _run(bench, [str(config), "--", "--models", "m", "--task-group", "spot"], env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    args = (tmp / "run-args").read_text().splitlines()
    assert args[:4] == ["--backend", "openai-ext", "--ext-url", f"http://127.0.0.1:{env['STRATA_PORT']}"]
    assert args[4:6] == ["--ext-label", "strata-niko unknown my-model"]
    assert args[6:] == ["--models", "m", "--task-group", "spot"]
    assert _server_gone(tmp)


def test_a_fork_is_labelled_by_strata_engine(rig):
    tmp, bench, config, env = rig
    proc = _run(bench, [str(config), "--", "--models", "m"], env | {"STRATA_ENGINE": "edge0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "strata-edge0 unknown my-model" in (tmp / "run-args").read_text()


def test_ro99_mode_names_the_model_id_and_puts_wsl_libcuda_first(rig):
    tmp, bench, _, env = rig
    proc = _run(bench, ["--ro99", "--model", "models/gemma4", "--model-id", "gemma4", "--", "--models", "m"], env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "strata-ro99 unknown gemma4" in (tmp / "run-args").read_text()
    if Path("/usr/lib/wsl/lib").is_dir():
        assert (tmp / "server-env").read_text().split(":")[0] == "/usr/lib/wsl/lib"
    assert _server_gone(tmp)


def test_refuses_when_the_port_already_answers(rig):
    tmp, bench, config, env = rig

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    occupant = HTTPServer(("127.0.0.1", int(env["STRATA_PORT"])), H)
    Thread(target=occupant.serve_forever, daemon=True).start()
    try:
        proc = _run(bench, [str(config), "--", "--models", "m"], env)
    finally:
        occupant.shutdown()
    assert proc.returncode == 1 and "already answers" in proc.stderr
    assert not (tmp / "run-args").exists()


def test_a_server_that_dies_while_loading_fails_the_run_with_its_log(rig):
    tmp, bench, config, env = rig
    proc = _run(bench, [str(config), "--", "--models", "m"], env | {"STAND_IN_CRASH": "1"})
    assert proc.returncode == 1
    assert "exited during load" in proc.stderr and "engine failed to load" in proc.stderr
    assert not (tmp / "run-args").exists()
