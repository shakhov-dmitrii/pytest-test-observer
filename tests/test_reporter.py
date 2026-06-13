from __future__ import annotations

import pytest

from pytest_test_observer import buffer
from pytest_test_observer import reporter as reporter_module
from pytest_test_observer.reporter import ClickHouseReporter, parse_url


@pytest.mark.parametrize(
    "url,expected",
    [
        # Bare hostname → default port 8123, insecure
        ("clickhouse.internal", ("clickhouse.internal", 8123, False)),
        ("localhost", ("localhost", 8123, False)),
        # host:port form → explicit port, insecure
        ("localhost:8123", ("localhost", 8123, False)),
        ("ch.internal:9000", ("ch.internal", 9000, False)),
        # http://... → insecure, explicit port
        ("http://localhost:8123", ("localhost", 8123, False)),
        # http://... without port → default 8123
        ("http://ch.internal", ("ch.internal", 8123, False)),
        # https://... → secure=True, explicit port
        ("https://ch.internal:8443", ("ch.internal", 8443, True)),
        # https://... without port → default 8443 (the secure default)
        ("https://ch.internal", ("ch.internal", 8443, True)),
    ],
)
def test_parse_url_matrix(url, expected):
    assert parse_url(url) == expected


def test_reporter_rejects_unsafe_table_name():
    from pytest_test_observer.schema import SchemaError

    with pytest.raises(SchemaError):
        ClickHouseReporter(
            url="localhost:8123", user="default", password="", db="default", table="bad-name"
        )


def _make_reporter() -> ClickHouseReporter:
    return ClickHouseReporter(
        url="localhost:8123",
        user="default",
        password="",
        db="default",
        table="t",
        auto_migrate=True,
    )


def test_flush_buffers_to_disk_on_failure_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def boom(**kwargs):
        raise ConnectionError("clickhouse down")

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", boom)

    ok = _make_reporter().flush([{"nodeid": "t1"}], "run-a")
    assert ok is False
    assert (buffer.buffer_dir() / "run-a.jsonl").exists()


def test_flush_skips_disk_buffer_when_buffer_on_failure_false(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def boom(**kwargs):
        raise ConnectionError("clickhouse down")

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", boom)

    ok = _make_reporter().flush([{"nodeid": "t1"}], "run-a", buffer_on_failure=False)
    assert ok is False
    assert not (buffer.buffer_dir() / "run-a.jsonl").exists()


def test_flush_events_skips_disk_buffer_when_buffer_on_failure_false(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def boom(**kwargs):
        raise ConnectionError("clickhouse down")

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", boom)

    ok = _make_reporter().flush_events([{"event_name": "x"}], "run-a", buffer_on_failure=False)
    assert ok is False
    assert not (buffer.buffer_dir() / "run-a_events.jsonl").exists()


def test_flush_events_buffers_to_disk_on_failure_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def boom(**kwargs):
        raise ConnectionError("clickhouse down")

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", boom)

    ok = _make_reporter().flush_events([{"event_name": "x"}], "run-a")
    assert ok is False
    assert (buffer.buffer_dir() / "run-a_events.jsonl").exists()


def test_flush_clears_cached_client_on_failure(monkeypatch):
    call_count = {"n": 0}

    class _Client:
        def __init__(self, fail: bool):
            self.fail = fail
            self.inserted = False

        def command(self, sql):
            pass

        def query(self, sql, parameters=None):
            from types import SimpleNamespace

            from pytest_test_observer.schema import EXPECTED_SCHEMA

            return SimpleNamespace(result_rows=list(EXPECTED_SCHEMA.items()))

        def insert(self, table, data, column_names):
            if self.fail:
                raise ConnectionError("transient")
            self.inserted = True

    def factory(**kwargs):
        call_count["n"] += 1
        return _Client(fail=(call_count["n"] == 1))

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", factory)

    reporter = _make_reporter()
    row = {c: "" for c in __import__("pytest_test_observer.schema", fromlist=["COLUMNS"]).COLUMNS}
    row["duration"] = 0.0
    row["started_at"] = 0
    row["finished_at"] = 0
    row["markers"] = []
    row["allure_labels"] = {}
    row["allure_links"] = []

    assert reporter.flush([row], "r1", buffer_on_failure=False) is False
    assert reporter._client is None
    assert reporter.flush([row], "r2", buffer_on_failure=False) is True
    assert call_count["n"] == 2
