from __future__ import annotations

import enum

import pytest

from pytest_test_observer.helper import as_bool, as_str


class _Severity(str, enum.Enum):
    CRITICAL = "critical"
    NORMAL = "normal"


class _Plain(enum.Enum):
    A = 1
    B = 2


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
        (True, True),
        (False, False),
        (None, False),  # uses default
    ],
)
def test_as_bool_recognises_common_values(value, expected):
    assert as_bool(value) is expected


def test_as_bool_returns_default_for_garbage():
    assert as_bool("maybe", default=True) is True
    assert as_bool("maybe", default=False) is False


def test_as_bool_none_uses_default():
    assert as_bool(None, default=True) is True
    assert as_bool(None, default=False) is False


def test_as_bool_passes_real_bools_through():
    assert as_bool(True) is True
    assert as_bool(False) is False


def test_str_unwraps_str_enum_to_value():
    assert as_str(_Severity.CRITICAL) == "critical"


def test_str_unwraps_plain_enum_to_value():
    assert as_str(_Plain.A) == "1"


def test_str_passes_plain_strings_through():
    assert as_str("hello") == "hello"


def test_str_stringifies_arbitrary_objects():
    assert as_str(42) == "42"
    assert as_str(None) == "None"
