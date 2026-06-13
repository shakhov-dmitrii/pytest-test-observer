from __future__ import annotations

import json
import os
import time
import warnings
from urllib.parse import urlparse

import clickhouse_connect

from pytest_test_observer import buffer
from pytest_test_observer.constants import EVENTS_SUFFIX
from pytest_test_observer.events import (
    CREATE_EVENTS_TABLE_SQL,
    EVENTS_COLUMNS,
    EVENTS_EXPECTED_SCHEMA,
)
from pytest_test_observer.schema import (
    COLUMNS,
    CREATE_TABLE_SQL,
    EXPECTED_SCHEMA,
    ensure_schema,
    validate_table_name,
)

_METRICS_ENV = "PYTEST_OBSERVER_METRICS_FILE"


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
        self.table = validate_table_name(table)
        self.auto_migrate = auto_migrate
        self._client = None

    def _get_client(self):
        if self._client is None:
            host, port, secure = parse_url(self.url)
            self._client = clickhouse_connect.get_client(
                host=host,
                port=port,
                username=self.user,
                password=self.password,
                database=self.db,
                secure=secure,
                connect_timeout=5,
                send_receive_timeout=10,
            )
        return self._client

    def flush(self, rows: list, run_id: str, *, buffer_on_failure: bool = True) -> bool:
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
            client = self._get_client()
            client.command(CREATE_TABLE_SQL.format(table=self.table))
            added = ensure_schema(
                client, self.table, auto_migrate=self.auto_migrate, expected=EXPECTED_SCHEMA
            )
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
            # Drop the cached client so the next call reconnects rather than
            # reusing one whose connection is in an unknown state.
            self._client = None
            if not buffer_on_failure:
                warnings.warn(
                    f"[pytest-test-observer] flush results to ClickHouse failed: {exc!r}",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    f"[pytest-test-observer] flush results to ClickHouse failed: {exc!r}; "
                    f"writing {len(rows)} rows to disk buffer",
                    stacklevel=2,
                )
                try:
                    path = buffer.write_jsonl(rows, run_id)
                    warnings.warn(
                        f"[pytest-test-observer] results buffered to {path}",
                        stacklevel=2,
                    )
                except Exception as exc2:
                    warnings.warn(
                        f"[pytest-test-observer] results disk buffer also failed: {exc2!r}",
                        stacklevel=2,
                    )
        finally:
            metrics["flush_seconds"] = time.perf_counter() - start
            _maybe_write_metrics(metrics)
        return metrics["ok"]

    def flush_events(self, rows: list, run_id: str, *, buffer_on_failure: bool = True) -> bool:
        if not rows:
            return True
        events_table = f"{self.table}_events"
        ok = False
        try:
            client = self._get_client()
            client.command(CREATE_EVENTS_TABLE_SQL.format(table=events_table))
            added = ensure_schema(
                client,
                events_table,
                auto_migrate=self.auto_migrate,
                expected=EVENTS_EXPECTED_SCHEMA,
            )
            if added:
                warnings.warn(
                    f"[pytest-test-observer] auto-migrated {events_table!r}: added columns {added}",
                    stacklevel=2,
                )
            data = [[row[c] for c in EVENTS_COLUMNS] for row in rows]
            client.insert(events_table, data, column_names=list(EVENTS_COLUMNS))
            ok = True
        except Exception as exc:
            # Drop the cached client so the next call reconnects rather than
            # reusing one whose connection is in an unknown state.
            self._client = None
            if not buffer_on_failure:
                warnings.warn(
                    f"[pytest-test-observer] flush events to ClickHouse failed: {exc!r}",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    f"[pytest-test-observer] flush events to ClickHouse failed: {exc!r}; "
                    f"writing {len(rows)} events to disk buffer",
                    stacklevel=2,
                )
                try:
                    path = buffer.write_jsonl(rows=rows, run_id=run_id, suffix=EVENTS_SUFFIX)
                    warnings.warn(
                        f"[pytest-test-observer] events buffered to {path}",
                        stacklevel=2,
                    )
                except Exception as exc2:
                    warnings.warn(
                        f"[pytest-test-observer] events disk buffer also failed: {exc2!r}",
                        stacklevel=2,
                    )
        return ok


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
