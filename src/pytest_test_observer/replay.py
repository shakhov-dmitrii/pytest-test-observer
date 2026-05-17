"""Replay buffered JSONL files back into ClickHouse.

When a session-end flush fails (network down, CH unreachable, timeout, etc.),
each session's rows are written to
``$XDG_CACHE_HOME/pytest-test-observer/<run_id>.jsonl``. This tool reads those
files, parses each line, and pushes the rows to ClickHouse. On success the
buffer file is deleted; on failure it's recreated by the reporter's fallback
path so a later replay can pick up where this one left off.

Invocation:

    python -m pytest_test_observer.replay --ch-url=localhost:8123
    python -m pytest_test_observer.replay /path/to/specific.jsonl
    python -m pytest_test_observer.replay --dry-run

Options mirror the plugin (``--ch-url``, ``--ch-user``, ``--ch-password``,
``--ch-db``, ``--ch-table``, ``--ch-auto-migrate``) and pick up the same
``PYTEST_OBSERVER_CH_*`` env vars when set.

Forward-compatibility with older schemas: rows missing any current column
get a sensible default (empty string / 0 / empty array), so a JSONL file
written by an older plugin version replays cleanly into the latest table.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

from pytest_test_observer.buffer import buffer_dir
from pytest_test_observer.helper import as_bool
from pytest_test_observer.reporter import ClickHouseReporter
from pytest_test_observer.schema import SCHEMA

_DEFAULT_FOR_TYPE: dict = {
    "String": "",
    "DateTime64(3)": "",  # ISO string accepted by clickhouse-connect
    "UInt64": 0,
    "Float64": 0.0,
    "LowCardinality(String)": "",
    "Array(String)": [],
    "Map(String, Array(String))": {},
    "Array(Tuple(String, String, String))": [],
}

# Pre-compute per-column defaults so the inner loop is cheap.
_COLUMN_DEFAULTS: dict = {name: _DEFAULT_FOR_TYPE.get(type_, "") for name, type_ in SCHEMA}


def parse_jsonl_text(text: str) -> tuple[list, int]:
    rows: list = []
    skipped = 0
    for line_num, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            warnings.warn(
                f"[replay] line {line_num}: not valid JSON ({exc}); skipping",
                stacklevel=2,
            )
            skipped += 1
            continue
        if not isinstance(row, dict):
            warnings.warn(
                f"[replay] line {line_num}: not a JSON object; skipping",
                stacklevel=2,
            )
            skipped += 1
            continue
        for col, default in _COLUMN_DEFAULTS.items():
            row.setdefault(col, default)
        rows.append(row)
    return rows, skipped


def replay_file(reporter: ClickHouseReporter, path: Path, *, keep: bool) -> tuple[int, int, bool]:
    text = path.read_text(encoding="utf-8")
    rows, skipped = parse_jsonl_text(text)
    if not rows:
        return 0, skipped, True
    if not keep:
        path.unlink()
    ok = reporter.flush(rows, path.stem)
    return len(rows), skipped, ok


def find_buffer_files(paths: list) -> list:
    if not paths:
        return sorted(buffer_dir().glob("*.jsonl"))
    files: list = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.glob("*.jsonl")))
        elif p.exists():
            files.append(p)
        else:
            warnings.warn(f"[replay] no such file or directory: {p}", stacklevel=2)
    return files


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pytest_test_observer.replay",
        description="Replay buffered JSONL files into ClickHouse.",
    )
    p.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="JSONL files or directories to replay (default: scan buffer dir)",
    )
    p.add_argument(
        "--ch-url",
        default=os.environ.get("PYTEST_OBSERVER_CH_URL"),
        help="ClickHouse URL (host, host:port, or http(s)://...) [required]",
    )
    p.add_argument("--ch-user", default=os.environ.get("PYTEST_OBSERVER_CH_USER", "default"))
    p.add_argument("--ch-password", default=os.environ.get("PYTEST_OBSERVER_CH_PASSWORD", ""))
    p.add_argument("--ch-db", default=os.environ.get("PYTEST_OBSERVER_CH_DB", "default"))
    p.add_argument(
        "--ch-table",
        default=os.environ.get("PYTEST_OBSERVER_CH_TABLE", "pytest_results"),
    )
    p.add_argument(
        "--ch-auto-migrate",
        default=os.environ.get("PYTEST_OBSERVER_CH_AUTO_MIGRATE", "true"),
        help="true/false; auto-add missing columns via ALTER TABLE",
    )
    p.add_argument(
        "--keep",
        action="store_true",
        help="don't delete buffer files after successful replay",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="list files that would be replayed; don't touch ClickHouse",
    )
    return p


def main(argv: list | None = None) -> int:
    args = _build_parser().parse_args(argv)
    files = find_buffer_files(args.paths)

    if not files:
        print("no buffer files found", file=sys.stderr)
        return 0

    if args.dry_run:
        for f in files:
            line_count = sum(
                1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip()
            )
            print(f"would replay {f}  ({line_count} lines)")
        return 0

    if not args.ch_url:
        print(
            "error: --ch-url is required (or set PYTEST_OBSERVER_CH_URL)",
            file=sys.stderr,
        )
        return 2

    reporter = ClickHouseReporter(
        url=args.ch_url,
        user=args.ch_user,
        password=args.ch_password,
        db=args.ch_db,
        table=args.ch_table,
        auto_migrate=as_bool(args.ch_auto_migrate, default=True),
    )

    rows_total = 0
    skipped_total = 0
    failures: list = []
    for f in files:
        rows, skipped, ok = replay_file(reporter, f, keep=args.keep)
        rows_total += rows
        skipped_total += skipped
        status = "ok" if ok else "FAILED (re-buffered)"
        print(f"  {f}: {rows} rows, {skipped} skipped — {status}")
        if not ok:
            failures.append(f)

    print(
        f"\ndone: {rows_total} rows replayed across {len(files)} files; "
        f"{skipped_total} malformed lines skipped; {len(failures)} files failed."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
