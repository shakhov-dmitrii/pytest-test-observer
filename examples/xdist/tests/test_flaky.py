"""Flaky tests under xdist + rerun strategy.

A few things worth noting about the combination:

1. pytest-rerunfailures retries within the **same** xdist worker that owns
   the test (it operates inside that item's lifecycle). All attempts of one
   flaky test therefore share the same `worker_id` in ClickHouse — useful
   for "worker X seems to host all the flake" investigations.

2. The module-level counter trick still works: each worker is a separate
   Python process, but all retries of one test happen in the same process,
   so `_attempt_counts` accumulates as expected. The counter is *not*
   shared across workers, which is irrelevant here because each test only
   runs on one worker per session anyway.
"""

import allure
import pytest

_attempt_counts: dict = {}


def _bump(label: str) -> int:
    _attempt_counts[label] = _attempt_counts.get(label, 0) + 1
    return _attempt_counts[label]


@allure.feature("Reports")
@allure.story("Network calls")
@pytest.mark.flaky(reruns=3)
def test_flaky_passes_on_third_attempt():
    attempt = _bump("flaky_pass_3rd")
    if attempt < 3:
        raise AssertionError(f"flaky network blip on attempt {attempt}")
    assert True


@allure.feature("Reports")
@allure.story("Network calls")
@pytest.mark.flaky(reruns=3)
def test_flaky_exhausts_reruns():
    # Always fails — exhausts retries → final status: failed.
    attempt = _bump("flaky_always_fails")
    raise AssertionError(f"persistent failure (attempt {attempt})")


@allure.feature("Reports")
@allure.story("Network calls")
@pytest.mark.flaky(reruns=3)
@pytest.mark.parametrize("call_id", ["search", "checkout", "report"])
def test_flaky_per_endpoint(call_id):
    # Per-parameter counter — each parametrized case has its own retry
    # history. `search` passes immediately; `checkout` needs a retry;
    # `report` always fails.
    attempt = _bump(f"flaky_per_endpoint::{call_id}")
    if call_id == "search":
        assert True
    elif call_id == "checkout":
        if attempt < 2:
            raise AssertionError(f"checkout flaked on attempt {attempt}")
        assert True
    else:  # report
        raise AssertionError(f"report endpoint is broken (attempt {attempt})")
