"""_bool_flag: --load-mode none on llama-server builds that have it, --no-mmap on older ones."""
import stat
from pathlib import Path

from lib import llama_server_client as lsc

# Excerpts of real `llama-server --help` output: 67a17c17c (has --load-mode) and an older build.
_NEW_HELP = (
    "--mmap, --no-mmap   DEPRECATED in favor of `--load-mode`: whether to memory-map model.\n"
    "-lm, --load-mode {auto,none,mmap,mlock,mmap+mlock,dio}"
)
_OLD_HELP = "--mmap, --no-mmap   whether to memory-map model (default: enabled)"


def _fake_bin(tmp_path: Path, name: str, help_text: str) -> str:
    p = tmp_path / name
    p.write_text(f"#!/bin/sh\ncat <<'EOF'\n{help_text}\nEOF\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_no_mmap_becomes_load_mode_none_on_new_builds(tmp_path):
    assert lsc._bool_flag("no-mmap", _fake_bin(tmp_path, "new", _NEW_HELP)) == ["--load-mode", "none"]


def test_no_mmap_stays_legacy_on_old_builds(tmp_path):
    assert lsc._bool_flag("no-mmap", _fake_bin(tmp_path, "old", _OLD_HELP)) == ["--no-mmap"]


def test_missing_binary_falls_back_to_legacy_flag(tmp_path):
    assert lsc._bool_flag("no-mmap", str(tmp_path / "missing")) == ["--no-mmap"]


def test_other_bool_flags_unchanged(tmp_path):
    b = _fake_bin(tmp_path, "new2", _NEW_HELP)
    assert lsc._bool_flag("flash-attn", b) == ["--flash-attn", "on"]
    assert lsc._bool_flag("no-repack", b) == ["--no-repack"]


def test_help_is_read_once_per_binary(tmp_path):
    b = _fake_bin(tmp_path, "new3", _NEW_HELP)
    assert lsc._bool_flag("no-mmap", b) == ["--load-mode", "none"]
    Path(b).write_text("#!/bin/sh\necho nothing\n")
    assert lsc._bool_flag("no-mmap", b) == ["--load-mode", "none"]
