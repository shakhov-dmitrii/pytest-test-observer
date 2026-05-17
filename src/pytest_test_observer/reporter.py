from __future__ import annotations

import json
import os
import time
import warnings
from urllib.parse import urlparse

import clickhouse_connect

from pytest_test_observer import buffer
from pytest_test_observer.schema import COLUMNS, column_defs_sql, ensure_schema

_METRICS_ENV = "PYTEST_OBSERVER_METRICS_FILE"

# Re-export COLUMNS for callers that imported it from reporter (back-compat).
__all__ = ("COLUMNS", "CREATE_TABLE_SQL", "ClickHouseReporter", "parse_url")

CREATE_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS {table} (\n    "
    + column_defs_sql()
    + "\n) ENGINE = MergeTree\nORDER BY (nodeid, timestamp)\nPARTITION BY toYYYYMM(timestamp)"
)


class ClickHouseReporter:
    def __init__(
        self,
        *,
        url: str,
        user: str,
        password: str,
        db: str,
        table: str,
        auto_migrate: bool = True,
    ):
        self.url = url
        self.user = user
        self.password = password
        self.db = db
        self.table = table
        self.auto_migrate = auto_migrate

    def flush(self, rows: list, run_id: str) -> bool:
        if not rows:
            return True
        metrics = {
            "rows": len(rows),
            "bytes_written": 0,
            "flush_seconds": 0.0,
            "ok": False,
            "migrations_applied": [],
        }
        start = time.perf_counter()
        try:
            host, port, secure = parse_url(self.url)
            client = clickhouse_connect.get_client(
                host=host,
                port=port,
                username=self.user,
                password=self.password,
                database=self.db,
                secure=secure,
                connect_timeout=5,
                send_receive_timeout=10,
            )
            client.command(CREATE_TABLE_SQL.format(table=self.table))
            added = ensure_schema(client, self.table, auto_migrate=self.auto_migrate)
            if added:
                metrics["migrations_applied"] = added
                warnings.warn(
                    f"[pytest-test-observer] auto-migrated {self.table!r}: added columns {added}",
                    stacklevel=2,
                )
            data = [[row[c] for c in COLUMNS] for row in rows]
            summary = client.insert(self.table, data, column_names=list(COLUMNS))
            metrics["bytes_written"] = _summary_bytes(summary)
            metrics["ok"] = True
        except Exception as exc:
            warnings.warn(
                f"[pytest-test-observer] flush to ClickHouse failed: {exc!r}; "
                f"writing {len(rows)} rows to disk buffer",
                stacklevel=2,
            )
            try:
                path = buffer.write_jsonl(rows, run_id)
                warnings.warn(
                    f"[pytest-test-observer] buffered to {path}",
                    stacklevel=2,
                )
            except Exception as exc2:
                warnings.warn(
                    f"[pytest-test-observer] disk buffer also failed: {exc2!r}",
                    stacklevel=2,
                )
        finally:
            metrics["flush_seconds"] = time.perf_counter() - start
            _maybe_write_metrics(metrics)
        return metrics["ok"]


def _summary_bytes(summary) -> int:
    if summary is None:
        return 0
    payload = getattr(summary, "summary", None) or {}
    raw = payload.get("written_bytes") or payload.get("read_bytes") or 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _maybe_write_metrics(metrics: dict) -> None:
    path = os.environ.get(_METRICS_ENV)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics, f)
    except Exception:
        pass


def parse_url(url: str) -> tuple:
    if "://" in url:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        secure = parsed.scheme == "https"
        port = parsed.port or (8443 if secure else 8123)
        return host, port, secure
    if ":" in url:
        host, _, port_s = url.partition(":")
        return host, int(port_s), False
    return url, 8123, False
