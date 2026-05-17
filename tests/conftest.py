"""Test fixtures + helper classes shared across the suite."""

from __future__ import annotations

import pytest

from pytest_test_observer import context
from pytest_test_observer import reporter as reporter_module

pytest_plugins = ["pytester"]


# env-var stubs for buffer / plugin tests
@pytest.fixture
def xdg_cache_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))


@pytest.fixture
def isolate_buffer_and_run_id(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("PYTEST_OBSERVER_RUN_ID", "test-run-1")


# subprocess / external-tool stubs
@pytest.fixture
def git_not_installed(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("git: not found")

    monkeypatch.setattr(context.subprocess, "run", fake_run)


# pytester payloads for plugin scenarios
@pytest.fixture
def xdist_test_suite(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        def test_a():
            assert True

        def test_b():
            assert True

        def test_c():
            raise ValueError("boom")

        @pytest.mark.skip
        def test_d():
            pass
        """
    )
    return pytester


# fake ClickHouse client for plugin / reporter tests
class _SchemaQueryResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    def __init__(self):
        self.commands: list = []
        self.inserts: list = []
        from pytest_test_observer.schema import EXPECTED_SCHEMA

        self._columns: dict = dict(EXPECTED_SCHEMA)

    def command(self, sql):
        self.commands.append(sql)
        if "ADD COLUMN IF NOT EXISTS" in sql:
            tail = sql.split("ADD COLUMN IF NOT EXISTS", 1)[1].strip()
            name, type_ = tail.split(maxsplit=1)
            self._columns[name] = type_

    def insert(self, table, data, column_names):
        self.inserts.append((table, data, list(column_names)))

    def query(self, sql, parameters=None):
        return _SchemaQueryResult(list(self._columns.items()))


@pytest.fixture
def fake_clients(monkeypatch):
    created: list = []

    def factory(**kwargs):
        client = FakeClient()
        client.kwargs = kwargs
        created.append(client)
        return client

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", factory)
    return created
