import pytest
from config import load_config


def test_defaults(monkeypatch):
    for k in ("APP_HOST", "APP_PORT", "APP_DEBUG", "APP_MAX_CONN", "APP_NAME"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.host == "localhost"
    assert cfg.port == 8080
    assert cfg.debug is False
    assert cfg.max_connections == 10
    assert cfg.app_name == "myapp"


def test_custom_values(monkeypatch):
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "3000")
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("APP_MAX_CONN", "50")
    monkeypatch.setenv("APP_NAME", "testapp")
    cfg = load_config()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 3000
    assert cfg.debug is True
    assert cfg.max_connections == 50
    assert cfg.app_name == "testapp"


def test_whitespace_stripped(monkeypatch):
    monkeypatch.setenv("APP_PORT", "  9000  ")
    monkeypatch.setenv("APP_MAX_CONN", " 25 ")
    monkeypatch.setenv("APP_HOST", "  myhost  ")
    for k in ("APP_DEBUG", "APP_NAME"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.port == 9000
    assert cfg.max_connections == 25
    assert cfg.host == "myhost"


def test_empty_string_uses_default(monkeypatch):
    monkeypatch.setenv("APP_NAME", "")
    monkeypatch.setenv("APP_HOST", "")
    for k in ("APP_PORT", "APP_DEBUG", "APP_MAX_CONN"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.app_name == "myapp"
    assert cfg.host == "localhost"


def test_debug_false_variants(monkeypatch):
    for val in ("false", "FALSE", "0", "no", ""):
        monkeypatch.setenv("APP_DEBUG", val)
        cfg = load_config()
        assert cfg.debug is False, f"expected False for APP_DEBUG={val!r}"


def test_debug_true(monkeypatch):
    monkeypatch.setenv("APP_DEBUG", "true")
    cfg = load_config()
    assert cfg.debug is True

    monkeypatch.setenv("APP_DEBUG", "TRUE")
    cfg = load_config()
    assert cfg.debug is True
