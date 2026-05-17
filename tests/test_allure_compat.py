from __future__ import annotations

from types import SimpleNamespace

import pytest

from pytest_test_observer import allure_compat


class _Mark:
    def __init__(self, name, args=(), kwargs=None):
        self.name = name
        self.args = args
        self.kwargs = kwargs or {}


class _FakeItem:
    def __init__(self, marks, function=None):
        self._marks = marks
        self.function = function

    def iter_markers(self, name=None):
        for m in self._marks:
            if name is None or m.name == name:
                yield m


def test_extract_labels_severity_and_id():
    item = _FakeItem(
        [
            _Mark("allure_label", ("Auth",), {"label_type": "feature"}),
            _Mark("allure_label", ("Login",), {"label_type": "story"}),
            _Mark("allure_label", ("smoke", "regression"), {"label_type": "tag"}),
            _Mark("allure_label", ("critical",), {"label_type": "severity"}),
            _Mark("allure_label", ("TC-101",), {"label_type": "as_id"}),
        ]
    )
    meta = allure_compat.extract_allure_meta(item)
    assert meta["labels"] == {
        "feature": ["Auth"],
        "story": ["Login"],
        "tag": ["smoke", "regression"],
        "severity": ["critical"],
        "as_id": ["TC-101"],
    }
    assert meta["severity"] == "critical"
    assert meta["allure_id"] == "TC-101"


def test_extract_links():
    item = _FakeItem(
        [
            _Mark("allure_link", ("https://issues/1",), {"link_type": "issue", "name": "Bug 1"}),
            _Mark("allure_link", ("https://x",), {"link_type": "link", "name": ""}),
        ]
    )
    meta = allure_compat.extract_allure_meta(item)
    assert meta["links"] == [
        ("issue", "https://issues/1", "Bug 1"),
        ("link", "https://x", ""),
    ]


def test_extract_title_from_function_attribute():
    def fake_test():
        pass

    fake_test.__allure_display_name__ = "Custom title"
    item = _FakeItem([], function=fake_test)
    meta = allure_compat.extract_allure_meta(item)
    assert meta["title"] == "Custom title"


def test_extract_empty_when_no_markers():
    meta = allure_compat.extract_allure_meta(_FakeItem([]))
    assert meta == {
        "labels": {},
        "links": [],
        "title": "",
        "severity": "",
        "allure_id": "",
    }


def test_extract_ignores_label_without_type():
    item = _FakeItem([_Mark("allure_label", ("orphan",), {})])
    meta = allure_compat.extract_allure_meta(item)
    assert meta["labels"] == {}


def test_extract_unwraps_str_enum_values():
    import enum

    class LabelType(str, enum.Enum):
        FEATURE = "feature"
        SEVERITY = "severity"

    class Severity(str, enum.Enum):
        CRITICAL = "critical"

    item = _FakeItem(
        [
            _Mark("allure_label", ("Auth",), {"label_type": LabelType.FEATURE}),
            _Mark("allure_label", (Severity.CRITICAL,), {"label_type": LabelType.SEVERITY}),
        ]
    )
    meta = allure_compat.extract_allure_meta(item)
    assert meta["labels"] == {"feature": ["Auth"], "severity": ["critical"]}
    assert meta["severity"] == "critical"


@pytest.mark.parametrize(
    "report_attrs,expected",
    [
        (dict(passed=True, failed=False, skipped=False, when="call", outcome="passed"), "passed"),
        (dict(passed=False, failed=True, skipped=False, when="call", outcome="failed"), "failed"),
        (dict(passed=False, failed=True, skipped=False, when="setup", outcome="failed"), "broken"),
        (
            dict(passed=False, failed=True, skipped=False, when="teardown", outcome="failed"),
            "broken",
        ),
        (dict(passed=False, failed=False, skipped=True, when="call", outcome="skipped"), "skipped"),
        (
            dict(passed=False, failed=False, skipped=True, when="setup", outcome="skipped"),
            "skipped",
        ),
        # pytest-rerunfailures: a failed attempt scheduled for retry
        (dict(passed=False, failed=False, skipped=False, when="call", outcome="rerun"), "failed"),
        (dict(passed=False, failed=False, skipped=False, when="setup", outcome="rerun"), "broken"),
    ],
)
def test_map_status_matrix(report_attrs, expected):
    report = SimpleNamespace(**report_attrs)
    assert allure_compat.map_status(report) == expected


def test_detect_allure_present():
    class PM:
        def hasplugin(self, name):
            return name == "allure_pytest"

    assert allure_compat.detect_allure(PM()) is True


def test_detect_allure_absent():
    class PM:
        def hasplugin(self, name):
            return False

    assert allure_compat.detect_allure(PM()) is False
