"""On-disk JSONL fallback for batches we couldn't push to ClickHouse."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_BUFFER_SUBDIR = "pytest-test-observer"
_EXTENSION = ".jsonl"

# Whitelist of characters allowed verbatim in run_id-derived filenames.
# Anything else (including path separators and `..`) is mapped to '_'.
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
# OS filename limits hover around 255 bytes; leave headroom for the
# extension and any pathological multi-byte inputs.
_MAX_RUN_ID = 128


def buffer_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / _BUFFER_SUBDIR


def write_jsonl(rows: list[dict], run_id: str) -> Path:
    safe_id = _sanitize_run_id(run_id)
    path = buffer_dir() / f"{safe_id}{_EXTENSION}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return path
    content = "\n".join(json.dumps(row, default=_json_default) for row in rows) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(content)
    return path


def _sanitize_run_id(run_id: str) -> str:
    cleaned = _UNSAFE_CHARS.sub("_", run_id or "")[:_MAX_RUN_ID]
    return cleaned or "unknown"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat(timespec="milliseconds")
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
