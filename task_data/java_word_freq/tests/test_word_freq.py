import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).parent.parent


def test_word_freq():
    if not shutil.which("javac"):
        raise RuntimeError(
            "javac not found — install JDK (not just JRE).\n"
            "  Ubuntu/WSL: sudo apt install default-jdk\n"
            "  Or set JAVA_HOME to a JDK installation."
        )
    with tempfile.TemporaryDirectory() as out:
        compile_result = subprocess.run(
            [
                "javac", "-d", out,
                str(ROOT / "WordFreq.java"),
                str(ROOT / "WordFreqTest.java"),
            ],
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, \
            "Compilation failed:\n" + compile_result.stderr

        run_result = subprocess.run(
            ["java", "-cp", out, "WordFreqTest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert run_result.returncode == 0, \
            run_result.stdout + run_result.stderr
