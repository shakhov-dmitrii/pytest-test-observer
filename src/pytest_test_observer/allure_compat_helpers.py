from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_test_observer.constants import (
    DISPLAY_NAME_ATTR,
    LABEL_MARK,
    LABEL_TYPE_KEY,
    LINK_MARK,
    LINK_NAME_KEY,
    LINK_TYPE_KEY,
)
from pytest_test_observer.helper import as_str

if TYPE_CHECKING:
    import pytest


def extract_labels(item: pytest.Item) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    for mark in item.iter_markers(LABEL_MARK):
        label_type = mark.kwargs.get(LABEL_TYPE_KEY)
        if label_type is None:
            continue
        type_str = as_str(label_type)
        for value in mark.args:
            labels.setdefault(type_str, []).append(as_str(value))
    return labels


def extract_links(item: pytest.Item) -> list[tuple[str, str, str]]:
    links: list[tuple[str, str, str]] = []
    for mark in item.iter_markers(LINK_MARK):
        if not mark.args:
            continue
        url = as_str(mark.args[0])
        link_type = as_str(mark.kwargs.get(LINK_TYPE_KEY, ""))
        link_name = as_str(mark.kwargs.get(LINK_NAME_KEY, ""))
        links.append((link_type, url, link_name))
    return links


def read_allure_title(item: pytest.Item) -> str:
    func = getattr(item, "function", None) or getattr(item, "obj", None)
    if func is None:
        return ""
    return str(getattr(func, DISPLAY_NAME_ATTR, "") or "")


def first_label_value(labels: dict[str, list[str]], key: str) -> str:
    values = labels.get(key, ())
    return values[0] if values else ""
