from __future__ import annotations

import pytest

from pytest_test_observer.schema import (
    COLUMNS,
    EXPECTED_SCHEMA,
    SCHEMA,
    SchemaError,
    column_defs_sql,
    ensure_schema,
)


class FakeQueryResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    """Minimal stand-in for clickhouse-connect's Client."""

    def __init__(self, columns: dict):
        self._columns = dict(columns)
        self.commands: list = []

    def query(self, sql: str, parameters=None):
        return FakeQueryResult([(name, type_) for name, type_ in self._columns.items()])

    def command(self, sql: str):
        self.commands.append(sql)
        if "ADD COLUMN IF NOT EXISTS" in sql:
            parts = sql.split("ADD COLUMN IF NOT EXISTS", 1)[1].strip().split(maxsplit=1)
            self._columns[parts[0]] = parts[1]


def test_columns_matches_schema_order():
    assert tuple(name for name, _ in SCHEMA) == COLUMNS


def test_expected_schema_keyed_by_name():
    assert set(EXPECTED_SCHEMA) == set(COLUMNS)


def test_column_defs_sql_renders_every_column():
    sql = column_defs_sql()
    for name, type_ in SCHEMA:
        assert f"{name} {type_}" in sql


def test_ensure_schema_no_op_when_table_matches():
    client = FakeClient(EXPECTED_SCHEMA)
    added = ensure_schema(client, "t", auto_migrate=True)
    assert added == []
    assert client.commands == []


def test_ensure_schema_auto_adds_missing_columns():
    partial = {name: EXPECTED_SCHEMA[name] for name in COLUMNS[:5]}
    client = FakeClient(partial)

    added = ensure_schema(client, "old_table", auto_migrate=True)

    assert added == list(COLUMNS[5:])
    assert len(client.commands) == len(COLUMNS) - 5
    assert all(
        c.startswith("ALTER TABLE old_table ADD COLUMN IF NOT EXISTS") for c in client.commands
    )


def test_ensure_schema_refuses_when_auto_migrate_disabled():
    partial = {name: EXPECTED_SCHEMA[name] for name in COLUMNS[:5]}
    client = FakeClient(partial)

    with pytest.raises(SchemaError) as exc:
        ensure_schema(client, "t", auto_migrate=False)

    msg = str(exc.value)
    assert "missing" in msg.lower()
    assert "ch_auto_migrate" in msg
    assert "ALTER TABLE t ADD COLUMN" in msg
    assert client.commands == []


def test_ensure_schema_raises_on_type_mismatch_regardless_of_flag():
    actual = dict(EXPECTED_SCHEMA)
    actual["status"] = "String"
    client = FakeClient(actual)

    with pytest.raises(SchemaError) as exc:
        ensure_schema(client, "t", auto_migrate=True)
    assert "incompatible" in str(exc.value).lower()
    assert "status" in str(exc.value)
    assert client.commands == []


def test_ensure_schema_ignores_extra_columns():
    actual = dict(EXPECTED_SCHEMA)
    actual["future_column_we_dont_know_about"] = "String"
    client = FakeClient(actual)

    added = ensure_schema(client, "t", auto_migrate=True)
    assert added == []
    assert client.commands == []


def test_ensure_schema_ignores_whitespace_differences_in_types():
    # ClickHouse may return types with slightly different spacing.
    actual = {
        "run_id": "String",
        "allure_labels": "Map(String,Array(String))",
    }
    actual.update({k: v for k, v in EXPECTED_SCHEMA.items() if k not in actual})
    client = FakeClient(actual)
    added = ensure_schema(client, "t", auto_migrate=False)
    assert added == []
