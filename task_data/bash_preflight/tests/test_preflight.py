import os
import subprocess
import pytest

SCRIPT = "preflight.sh"

_base = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "APP_SECRET")}


def run(**extra):
    env = {**_base, **extra}
    return subprocess.run(
        ["bash", SCRIPT],
        capture_output=True, text=True, env=env,
    )


def test_passes_when_all_present():
    r = run(DATABASE_URL="postgres://localhost/db", APP_SECRET="s3cr3t")
    assert r.returncode == 0
    assert "OK" in r.stdout


def test_fails_when_database_url_missing():
    r = run(APP_SECRET="s3cr3t")
    assert r.returncode != 0
    assert "MISSING_VAR" in r.stderr
    assert "DATABASE_URL" in r.stderr


def test_fails_when_app_secret_missing():
    r = run(DATABASE_URL="postgres://localhost/db")
    assert r.returncode != 0
    assert "MISSING_VAR" in r.stderr
    assert "APP_SECRET" in r.stderr


def test_fails_when_both_vars_missing():
    r = run()
    assert r.returncode != 0


def test_fails_when_var_is_empty_string():
    r = run(DATABASE_URL="", APP_SECRET="s3cr3t")
    assert r.returncode != 0
    assert "DATABASE_URL" in r.stderr


def test_no_ok_on_failure():
    r = run()
    assert "OK" not in r.stdout


def test_ok_not_printed_on_partial_failure():
    r = run(DATABASE_URL="postgres://localhost/db")  # APP_SECRET missing
    assert "OK" not in r.stdout
