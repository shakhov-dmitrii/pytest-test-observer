"""ClickHouse schema definition + diff/migrate helpers."""

from __future__ import annotations

import re

SCHEMA: tuple = (
    ("run_id", "String"),
    ("timestamp", "DateTime64(3)"),
    ("started_at", "UInt64"),
    ("finished_at", "UInt64"),
    ("nodeid", "String"),
    ("status", "LowCardinality(String)"),
    ("when_phase", "LowCardinality(String)"),
    ("duration", "Float64"),
    ("markers", "Array(String)"),
    ("worker_id", "LowCardinality(String)"),
    ("ci_provider", "LowCardinality(String)"),
    ("ci_run_id", "String"),
    ("git_commit", "String"),
    ("git_branch", "String"),
    ("allure_id", "String"),
    ("allure_title", "String"),
    ("allure_severity", "LowCardinality(String)"),
    ("allure_labels", "Map(String, Array(String))"),
    ("allure_links", "Array(Tuple(String, String, String))"),
)

EXPECTED_SCHEMA: dict = dict(SCHEMA)
COLUMNS: tuple = tuple(name for name, _ in SCHEMA)


def column_defs_sql() -> str:
    return ",\n    ".join(f"{name} {type_}" for name, type_ in SCHEMA)


class SchemaError(Exception):
    """Raised when the ClickHouse table can't be safely migrated."""


def ensure_schema(client, table: str, *, auto_migrate: bool) -> list:
    actual = _read_actual_columns(client, table)

    type_mismatches = [
        (name, actual[name], expected_type)
        for name, expected_type in EXPECTED_SCHEMA.items()
        if name in actual and not _types_compatible(actual[name], expected_type)
    ]
    if type_mismatches:
        details = "; ".join(f"{n} has {a!r}, expected {e!r}" for n, a, e in type_mismatches)
        raise SchemaError(
            f"ClickHouse table {table!r} has incompatible column types ({details}). "
            "This requires a manual migration — either DROP and recreate the table "
            "(loses history) or ALTER TABLE MODIFY COLUMN with appropriate care."
        )

    missing = [(name, type_) for name, type_ in EXPECTED_SCHEMA.items() if name not in actual]
    if not missing:
        return []

    if not auto_migrate:
        sql = "; ".join(f"ALTER TABLE {table} ADD COLUMN {name} {type_}" for name, type_ in missing)
        raise SchemaError(
            f"ClickHouse table {table!r} is missing {len(missing)} column(s) "
            f"and ch_auto_migrate is disabled. Run manually:\n  {sql}"
        )

    for name, type_ in missing:
        client.command(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {type_}")
    return [name for name, _ in missing]


def _read_actual_columns(client, table: str) -> dict:
    result = client.query(
        "SELECT name, type FROM system.columns "
        "WHERE database = currentDatabase() AND table = {table:String}",
        parameters={"table": table},
    )
    return {row[0]: row[1] for row in result.result_rows}


def _types_compatible(actual: str, expected: str) -> bool:
    return _normalize(actual) == _normalize(expected)


_WS_RE = re.compile(r"\s+")


def _normalize(t: str) -> str:
    return _WS_RE.sub("", t)
