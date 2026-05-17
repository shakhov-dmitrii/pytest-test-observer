from __future__ import annotations

from pytest_test_observer import options


class _FakeConfig:
    def __init__(self, *, cli=None, ini=None):
        self._cli = cli or {}
        self._ini = ini or {}

    def getoption(self, name):
        return self._cli.get(name)

    def getini(self, name):
        return self._ini.get(name)


def test_defaults_when_nothing_set():
    resolved = options.resolve_options(_FakeConfig())
    assert resolved == {
        "ch_url": None,
        "ch_user": "default",
        "ch_password": "",
        "ch_db": "default",
        "ch_table": "pytest_results",
        "ch_send_from": "any",
        "ch_auto_migrate": "true",
    }


def test_auto_migrate_can_be_disabled_via_ini():
    cfg = _FakeConfig(ini={"ch_auto_migrate": "false"})
    resolved = options.resolve_options(cfg)
    assert resolved["ch_auto_migrate"] == "false"


def test_auto_migrate_can_be_disabled_via_env(monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CH_AUTO_MIGRATE", "0")
    resolved = options.resolve_options(_FakeConfig())
    assert resolved["ch_auto_migrate"] == "0"


def test_send_from_can_be_set_from_env(monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CH_SEND_FROM", "ci")
    resolved = options.resolve_options(_FakeConfig())
    assert resolved["ch_send_from"] == "ci"


def test_send_from_can_be_set_from_ini():
    cfg = _FakeConfig(ini={"ch_send_from": "ci"})
    resolved = options.resolve_options(cfg)
    assert resolved["ch_send_from"] == "ci"


def test_ini_overrides_default():
    cfg = _FakeConfig(ini={"ch_url": "ini-host:8123", "ch_table": "ini_table"})
    resolved = options.resolve_options(cfg)
    assert resolved["ch_url"] == "ini-host:8123"
    assert resolved["ch_table"] == "ini_table"
    assert resolved["ch_user"] == "default"


def test_env_overrides_ini(monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CH_URL", "env-host:8123")
    monkeypatch.setenv("PYTEST_OBSERVER_CH_TABLE", "env_table")
    cfg = _FakeConfig(ini={"ch_url": "ini-host:8123", "ch_table": "ini_table"})
    resolved = options.resolve_options(cfg)
    assert resolved["ch_url"] == "env-host:8123"
    assert resolved["ch_table"] == "env_table"


def test_cli_overrides_env_and_ini(monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CH_URL", "env-host:8123")
    cfg = _FakeConfig(
        cli={"--ch-url": "cli-host:8123"},
        ini={"ch_url": "ini-host:8123"},
    )
    resolved = options.resolve_options(cfg)
    assert resolved["ch_url"] == "cli-host:8123"


def test_empty_string_env_is_respected():
    import os

    os.environ["PYTEST_OBSERVER_CH_PASSWORD"] = ""
    try:
        cfg = _FakeConfig(ini={"ch_password": "should-be-shadowed"})
        resolved = options.resolve_options(cfg)
        assert resolved["ch_password"] == ""
    finally:
        del os.environ["PYTEST_OBSERVER_CH_PASSWORD"]


def test_ini_only_picks_up_truthy_strings():
    cfg = _FakeConfig(ini={"ch_user": ""})
    resolved = options.resolve_options(cfg)
    assert resolved["ch_user"] == "default"
