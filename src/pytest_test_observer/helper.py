"""Small, plugin-agnostic value-normalisation helpers."""

from __future__ import annotations

import enum
from typing import Any


def as_str(value: Any) -> str:
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off", ""):
        return False
    return default
