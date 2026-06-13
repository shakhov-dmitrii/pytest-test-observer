"""Tests for the record_event fixture and events table flush."""

from __future__ import annotations

import json

import pytest

from pytest_test_observer import reporter as reporter_module
from pytest_test_observer.events import EVENTS_COLUMNS, EVENTS_SCHEMA, events_column_defs_sql

pytestmark = pytest.mark.usefixtures("isolate_buffer_and_run_id")


def test_events_schema_has_required_columns():
    cols = dict(EVENTS_SCHEMA)
    assert "run_id" in cols
    assert "nodeid" in cols
    assert "timestamp" in cols
    assert "seq" in cols
    assert "event_name" in cols
    assert "payload" in cols
    assert cols["payload"] == "Map(String, String)"
    assert cols["event_name"] == "LowCardinality(String)"


def test_events_column_defs_sql_renders_every_column():
    sql = events_column_defs_sql()
    for name, type_ in EVENTS_SCHEMA:
        assert f"{name} {type_}" in sql


def test_record_event_fixture_is_noop_when_plugin_inactive(pytester):
    pytester.makepyfile(
        """
        def test_with_events(record_event):
            record_event("cache_miss", {"key": "user:42"})
            record_event("retry", {"attempt": "2"})
            assert True
        """
    )
    result = pytester.runpytest_inprocess()
    result.assert_outcomes(passed=1)


def test_record_event_raises_on_non_string_payload_value(pytester):
    pytester.makepyfile(
        """
        def test_bad_payload(record_event):
            record_event("step", {"count": 42, "ok": True})
        """
    )
    result = pytester.runpytest_inprocess()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*TypeError*payload values must be str*"])


def test_events_are_flushed_to_events_table(pytester, fake_clients):
    pytester.makepyfile(
        """
        def test_with_events(record_event):
            record_event("cache_miss", {"key": "user:42"})
            record_event("retry", {"attempt": "2", "reason": "timeout"})
            assert True
        """
    )
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123", "--ch-table=t", "--custom-events=true"
    )
    result.assert_outcomes(passed=1)

    assert len(fake_clients) == 1
    client = fake_clients[0]

    assert len(client.inserts) == 2
    table, data, column_names = client.inserts[1]
    assert table == "t_events"
    assert column_names == list(EVENTS_COLUMNS)
    assert len(data) == 2

    seq_idx = column_names.index("seq")
    name_idx = column_names.index("event_name")
    payload_idx = column_names.index("payload")
    nodeid_idx = column_names.index("nodeid")

    rows_by_seq = {row[seq_idx]: row for row in data}
    assert rows_by_seq[0][name_idx] == "cache_miss"
    assert rows_by_seq[0][payload_idx] == {"key": "user:42"}
    assert rows_by_seq[1][name_idx] == "retry"
    assert rows_by_seq[1][payload_idx] == {"attempt": "2", "reason": "timeout"}

    nodeid = rows_by_seq[0][nodeid_idx]
    assert "test_with_events" in nodeid
    assert rows_by_seq[0][column_names.index("run_id")] == "test-run-1"


def test_events_sent_for_failed_test(pytester, fake_clients):
    pytester.makepyfile(
        """
        def test_fail(record_event):
            record_event("before_assert", {"value": "42"})
            assert False
        """
    )
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123", "--ch-table=t", "--custom-events=true"
    )
    result.assert_outcomes(failed=1)

    assert len(fake_clients) == 1
    client = fake_clients[0]
    assert len(client.inserts) == 2
    _, data, column_names = client.inserts[1]
    assert len(data) == 1
    assert data[0][column_names.index("event_name")] == "before_assert"


def test_multiple_calls_with_same_event_name(pytester, fake_clients):
    pytester.makepyfile(
        """
        def test_multi(record_event):
            record_event("step", {"n": "1"})
            record_event("step", {"n": "2"})
            record_event("step", {"n": "3"})
        """
    )
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123", "--ch-table=t", "--custom-events=true"
    )
    result.assert_outcomes(passed=1)

    _, data, column_names = fake_clients[0].inserts[1]
    assert len(data) == 3
    seq_idx = column_names.index("seq")
    payload_idx = column_names.index("payload")
    by_seq = sorted(data, key=lambda r: r[seq_idx])
    assert [r[payload_idx]["n"] for r in by_seq] == ["1", "2", "3"]


def test_no_events_does_not_create_events_client(pytester, fake_clients):
    pytester.makepyfile("def test_plain(): assert True")
    result = pytester.runpytest_inprocess("--ch-url=localhost:8123", "--ch-table=t")
    result.assert_outcomes(passed=1)

    assert len(fake_clients) == 1
    assert len(fake_clients[0].inserts) == 1


def test_custom_events_disabled_ignores_recorded_events(pytester, fake_clients):
    pytester.makepyfile(
        """
        def test_with_events(record_event):
            record_event("should_be_ignored", {"k": "v"})
        """
    )
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-table=t",
        "--custom-events=false",
    )
    result.assert_outcomes(passed=1)
    assert len(fake_clients) == 1
    assert len(fake_clients[0].inserts) == 1


def test_custom_events_disabled_via_env(pytester, fake_clients, monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CUSTOM_EVENTS", "false")
    pytester.makepyfile(
        """
        def test_with_events(record_event):
            record_event("should_be_ignored", {"k": "v"})
        """
    )
    result = pytester.runpytest_inprocess("--ch-url=localhost:8123", "--ch-table=t")
    result.assert_outcomes(passed=1)

    assert len(fake_clients) == 1


def test_events_buffered_to_disk_when_ch_down(pytester, monkeypatch, tmp_path):
    def boom_factory(**kwargs):
        raise ConnectionError("clickhouse down")

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", boom_factory)

    pytester.makepyfile(
        """
        def test_a(record_event):
            record_event("hit", {"cache": "yes"})
            assert True
        """
    )
    result = pytester.runpytest_inprocess("--ch-url=localhost:8123", "--custom-events=true")
    assert result.ret == 0

    events_path = tmp_path / "cache" / "pytest-test-observer" / "test-run-1_events.jsonl"
    assert events_path.exists(), f"expected events buffer at {events_path}"

    lines = events_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert ev["event_name"] == "hit"
    assert ev["payload"] == {"cache": "yes"}
    assert ev["run_id"] == "test-run-1"


def test_events_table_created_with_correct_name(pytester, fake_clients):
    pytester.makepyfile(
        """
        def test_x(record_event):
            record_event("ping", {})
        """
    )
    pytester.runpytest_inprocess(
        "--ch-url=localhost:8123", "--ch-table=myresults", "--custom-events=true"
    )

    client = fake_clients[0]
    create_cmds = [c for c in client.commands if "CREATE TABLE" in c]
    assert any("myresults_events" in c for c in create_cmds)
