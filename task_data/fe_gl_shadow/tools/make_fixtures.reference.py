#!/usr/bin/env python3
"""Fixtures for fe_gl_shadow: the scenes rendered with fastengine's own shadow code (Shadows.reference.cs) under
xvfb + llvmpipe, the same renderer the test uses.
Usage: python3 tools/make_fixtures.reference.py OUT_DIR   (normally tests/fixtures)"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as tmp:
    work = pathlib.Path(tmp) / "task"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("bin", "obj", "fixtures", "__pycache__", ".pytest_cache"))
    shutil.copy(work / "src/Fastengine/Shadows.reference.cs", work / "src/Fastengine/Shadows.cs")
    subprocess.run(["dotnet", "build", "tools/SceneRunner", "-v", "q", "-nologo", "-o", str(work / "bin")], cwd=work,
                   check=True, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    shots = pathlib.Path(tmp) / "shots"
    subprocess.run(["env", "LIBGL_ALWAYS_SOFTWARE=1", "xvfb-run", "-a", "-s", "-screen 0 640x480x24", "dotnet",
                    str(work / "bin/SceneRunner.dll"), str(shots)], cwd=work, check=True, stdin=subprocess.DEVNULL,
                   capture_output=True, timeout=180)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("noon.png", "evening.png"):
        shutil.copy(shots / name, out / name)
