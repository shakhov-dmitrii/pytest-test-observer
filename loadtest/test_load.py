"""Parametrized synthetic suite for load-testing the plugin.

Default: 20000 tests with a realistic outcome mix
  - 85% pass
  - 10% fail (call phase)
  -  3% skip (call phase, via pytest.skip)
  -  2% broken (setup phase, fixture raises)

Override the count with LOADTEST_COUNT.
"""

from __future__ import annotations

import os

import pytest

TEST_COUNT = int(os.environ.get("LOADTEST_COUNT", "20000"))


def _bucket(idx: int) -> str:
    n = idx % 100
    if n < 85:
        return "pass"
    if n < 95:
        return "fail"
    if n < 98:
        return "skip"
    return "broken"


@pytest.fixture(autouse=True)
def _maybe_break_setup(request):
    callspec = getattr(request.node, "callspec", None)
    if callspec is None:
        return
    idx = callspec.params.get("idx")
    if idx is not None and _bucket(idx) == "broken":
        raise RuntimeError(f"load: intentional setup break (idx={idx})")


@pytest.mark.parametrize("idx", range(TEST_COUNT))
def test_load(idx):
    outcome = _bucket(idx)
    if outcome == "fail":
        raise AssertionError(f"load: intentional failure (idx={idx})")
    if outcome == "skip":
        pytest.skip(f"load: intentional skip (idx={idx})")
    assert True


def expected_counts() -> dict:
    """What the load test should produce in ClickHouse, by status."""
    counts = {"passed": 0, "failed": 0, "skipped": 0, "broken": 0}
    for i in range(TEST_COUNT):
        b = _bucket(i)
        counts[{"pass": "passed", "fail": "failed", "skip": "skipped", "broken": "broken"}[b]] += 1
    return counts
