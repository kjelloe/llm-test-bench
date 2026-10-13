"""Drives scripts/version.sh against two throwaway git repos (fastengine and a game)."""
import datetime
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "version.sh"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30, env=ENV,
                          check=True).stdout.strip()


def repo(path, commit=True):
    path.mkdir()
    git(path, "init", "-q")
    (path / "README").write_text("x\n")
    if commit:
        git(path, "add", "README")
        git(path, "commit", "-q", "-m", "one")
    return path


@pytest.fixture
def repos(tmp_path):
    return repo(tmp_path / "fastengine"), repo(tmp_path / "game")


def stamp(fe, game):
    r = subprocess.run(["bash", str(SCRIPT), str(game)], cwd=fe, capture_output=True, text=True, timeout=30, env=ENV)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert len(lines) == 1, f"expected one line, got {r.stdout!r}"
    return lines[0]


def today():
    return datetime.date.today().strftime("%Y.%m.%d")


def short(path):
    return git(path, "rev-parse", "--short", "HEAD")


def test_clean_trees_name_both_commits(repos):
    fe, game = repos
    assert stamp(fe, game) == f"{today()}-{short(fe)}-{short(game)}"


@pytest.mark.parametrize("where", ["fe", "game"])
@pytest.mark.parametrize("change", ["edited", "staged", "untracked"])
def test_any_change_in_either_tree_is_dirty(repos, where, change):
    fe, game = repos
    tree = fe if where == "fe" else game
    if change == "edited":
        (tree / "README").write_text("y\n")
    elif change == "staged":
        (tree / "NEW").write_text("n\n")
        git(tree, "add", "NEW")
    else:
        (tree / "untracked.txt").write_text("u\n")
    assert stamp(fe, game) == f"{today()}-{short(fe)}-{short(game)}-dirty"


def test_a_repo_without_commits_is_uncommitted(tmp_path):
    fe = repo(tmp_path / "fastengine")
    game = repo(tmp_path / "game", commit=False)
    (game / "README").unlink()
    assert stamp(fe, game) == f"{today()}-{short(fe)}-uncommitted"


def test_new_commit_changes_the_stamp(repos):
    fe, game = repos
    before = stamp(fe, game)
    (game / "README").write_text("z\n")
    git(game, "commit", "-qam", "two")
    after = stamp(fe, game)
    assert after != before and after == f"{today()}-{short(fe)}-{short(game)}"
