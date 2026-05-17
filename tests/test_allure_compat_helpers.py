from __future__ import annotations

import pytest

from pytest_test_observer.allure_compat_helpers import first_label_value


def test_first_label_value_returns_first_when_multiple():
    labels = {"tag": ["smoke", "regression", "slow"]}
    assert first_label_value(labels, "tag") == "smoke"


def test_first_label_value_returns_only_value():
    labels = {"severity": ["critical"]}
    assert first_label_value(labels, "severity") == "critical"


def test_first_label_value_empty_when_key_missing():
    assert first_label_value({"feature": ["Auth"]}, "severity") == ""


def test_first_label_value_empty_when_dict_empty():
    assert first_label_value({}, "anything") == ""


def test_first_label_value_empty_when_value_list_empty():
    assert first_label_value({"feature": []}, "feature") == ""


@pytest.mark.parametrize(
    "labels,key,expected",
    [
        ({"a": ["x"]}, "a", "x"),
        ({"a": ["x", "y"]}, "a", "x"),
        ({"a": ["x"]}, "b", ""),
        ({}, "a", ""),
    ],
)
def test_first_label_value_matrix(labels, key, expected):
    assert first_label_value(labels, key) == expected
