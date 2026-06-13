"""Schema for the per-test events table ({table}_events)."""

from __future__ import annotations

from pytest_test_observer.schema import column_defaults

EVENTS_SCHEMA: tuple = (
    ("run_id", "String"),
    ("nodeid", "String"),
    ("timestamp", "DateTime64(3)"),
    ("seq", "UInt32"),
    ("event_name", "LowCardinality(String)"),
    ("payload", "Map(String, String)"),
)

EVENTS_COLUMNS: tuple = tuple(name for name, _ in EVENTS_SCHEMA)
EVENTS_EXPECTED_SCHEMA: dict = dict(EVENTS_SCHEMA)
EVENTS_COLUMN_DEFAULTS: dict = column_defaults(EVENTS_SCHEMA)


def events_column_defs_sql() -> str:
    return ",\n    ".join(f"{name} {type_}" for name, type_ in EVENTS_SCHEMA)


CREATE_EVENTS_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS {table} (\n    "
    + events_column_defs_sql()
    + "\n) ENGINE = MergeTree\nORDER BY (nodeid, timestamp, seq)\nPARTITION BY toYYYYMM(timestamp)"
)
