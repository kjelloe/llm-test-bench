"""scripts/stop_server.sh against real listening sockets. Each server's command line contains its
port, and so do a decoy process and the shell that runs the script, as they did in the incident
where `pkill -f <pattern>` killed the agent's own shell."""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent

SERVER = """
import signal, socket, sys, time
port, mode = int(sys.argv[1]), sys.argv[2]
if mode == "stubborn":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode.startswith("save:"):
    def save(*_):
        open(mode[5:], "w").write("saved")
        sys.exit(0)
    signal.signal(signal.SIGTERM, save)
s = socket.socket(socket.AF_INET6 if mode == "v6" else socket.AF_INET)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("::" if mode == "v6" else "127.0.0.1", port))
s.listen()
print("ready", flush=True)
while True:
    time.sleep(0.1)
"""


def mentioned(port):
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if str(port).encode() in cmdline.read_bytes():
                return True
        except OSError:
            pass
    return False


def free_port():
    # A broken script may `pkill -f <port>`: never pick a number another process's command line
    # already contains, so only the processes this test starts can match.
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if not mentioned(port):
            return port


def listening(port):
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return True
            except OSError:
                pass
    return False


@pytest.fixture
def procs():
    started = []
    yield started
    for p in started:
        if p.poll() is None:
            p.kill()
        p.wait()


def server(procs, port, mode="plain"):
    p = subprocess.Popen([sys.executable, "-c", SERVER, str(port), mode], stdout=subprocess.PIPE, text=True)
    procs.append(p)
    assert p.stdout.readline().strip() == "ready"
    return p


def decoy(procs, port):
    # Mentions the port on its command line but listens on nothing.
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", f"--watch-port={port}"])
    procs.append(p)
    return p


def stop(port):
    # The parent shell's command line contains the port too.
    script = TASK / "scripts" / "stop_server.sh"
    p = subprocess.run(["bash", "-c", f'bash "{script}" {port}; echo "exit=$?"; echo parent-alive {port}'],
                       capture_output=True, text=True, timeout=30)
    return p


def test_stops_the_listener_and_nothing_else(procs):
    port = free_port()
    srv, dec = server(procs, port), decoy(procs, port)
    p = stop(port)
    assert f"parent-alive {port}" in p.stdout, "the script killed the shell that ran it"
    assert "exit=0" in p.stdout, p.stdout + p.stderr
    assert f"stopped {srv.pid}" in p.stdout
    assert srv.wait(timeout=5) is not None
    assert not listening(port)
    assert dec.poll() is None, "the decoy that only mentions the port was killed"


def test_a_server_that_ignores_sigterm_is_killed(procs):
    port = free_port()
    srv = server(procs, port, "stubborn")
    start = time.monotonic()
    p = stop(port)
    assert "exit=0" in p.stdout, p.stdout + p.stderr
    assert srv.wait(timeout=1) == -signal.SIGKILL
    assert not listening(port)
    assert time.monotonic() - start < 10


def test_waits_until_the_port_is_free_before_returning(procs):
    port = free_port()
    server(procs, port, "stubborn")
    p = stop(port)
    assert "exit=0" in p.stdout, p.stdout + p.stderr
    with socket.socket() as s:  # the next smoke run binds right away
        s.bind(("127.0.0.1", port))


def test_a_well_behaved_server_gets_sigterm_and_can_save(procs, tmp_path):
    port, marker = free_port(), tmp_path / "saved"
    srv = server(procs, port, f"save:{marker}")
    p = stop(port)
    assert "exit=0" in p.stdout, p.stdout + p.stderr
    assert srv.wait(timeout=5) == 0
    assert marker.read_text() == "saved", "the server was not given SIGTERM first"


def test_ipv6_listener(procs):
    port = free_port()
    srv = server(procs, port, "v6")
    p = stop(port)
    assert "exit=0" in p.stdout, p.stdout + p.stderr
    assert srv.wait(timeout=5) is not None


def test_nothing_listening_is_an_error(procs):
    port = free_port()
    dec = decoy(procs, port)
    p = stop(port)
    assert f"parent-alive {port}" in p.stdout
    assert "exit=1" in p.stdout
    assert f"nothing listening on port {port}" in p.stderr
    assert dec.poll() is None


def test_a_different_port_is_left_alone(procs):
    port, other = free_port(), free_port()
    srv = server(procs, other)
    p = stop(port)
    assert "exit=1" in p.stdout
    assert srv.poll() is None
    assert listening(other)
