"""Compatibility layer for allure-pytest — the public API surface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_test_observer.allure_compat_helpers import (
    extract_labels,
    extract_links,
    first_label_value,
    read_allure_title,
)
from pytest_test_observer.constants import ID_LABEL, SEVERITY_LABEL, TestStatus
from pytest_test_observer.models import AllureMeta

if TYPE_CHECKING:
    import pytest

__all__ = ("AllureMeta", "detect_allure", "empty_allure_meta", "extract_allure_meta", "map_status")


def detect_allure(pluginmanager: Any) -> bool:
    return bool(pluginmanager.hasplugin("allure_pytest"))


def map_status(report: pytest.TestReport) -> TestStatus:
    """Map a pytest TestReport to the allure-style status vocabulary.

    Rules:
    - skipped → SKIPPED
    - passed  → PASSED
    - failed (call phase) → FAILED
    - failed (setup/teardown phase) → BROKEN  (allure convention)
    - outcome == 'rerun' (pytest-rerunfailures) → FAILED/BROKEN by phase
    - anything else → UNKNOWN
    """
    if report.skipped:
        return TestStatus.SKIPPED
    if report.passed:
        return TestStatus.PASSED
    if report.failed or report.outcome == TestStatus.RERUN:
        if report.when == "call":
            return TestStatus.FAILED
        if report.when in ("setup", "teardown"):
            return TestStatus.BROKEN
    return TestStatus.UNKNOWN


def extract_allure_meta(item: pytest.Item) -> AllureMeta:
    meta = empty_allure_meta()
    meta["labels"] = extract_labels(item)
    meta["links"] = extract_links(item)
    meta["title"] = read_allure_title(item)
    meta["severity"] = first_label_value(meta["labels"], SEVERITY_LABEL)
    meta["allure_id"] = first_label_value(meta["labels"], ID_LABEL)
    return meta


def empty_allure_meta() -> AllureMeta:
    return {
        "labels": {},
        "links": [],
        "title": "",
        "severity": "",
        "allure_id": "",
    }
