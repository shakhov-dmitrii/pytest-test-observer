"""Flaky-test patterns + rerun strategy via pytest-rerunfailures.

**Demo note:** the per-test "passes after N attempts" thresholds are randomised
per session so the dashboard sees varied attempt counts each run. Each retry
within a session uses the same threshold (set once at module load), so the
counter mechanism still works correctly.
"""

import os
import random

import pytest

_seed_env = os.environ.get("DEMO_SEED")
if _seed_env:
    random.seed(int(_seed_env) + 1)  # +1 so this file's randomness differs from test_user_flows

# Module-level threshold per test — picked once per pytest session.
# A threshold of N means "passes on attempt N", N=4 means "exhausts the 3 retries".
_thresholds: dict = {
    "flaky_pass_3rd": random.choice(
        [1, 2, 2, 3, 3, 4]
    ),  # weighted: usually flaky, sometimes resolves fast or never
    "flaky_always_fails": random.choice(
        [3, 4, 4, 4]
    ),  # mostly exhausts; sometimes "fixes itself" on attempt 3
    "flaky_custom": random.choice([1, 2, 3]),  # capped at 2 attempts via reruns=1
}

_attempt_counts: dict = {}


def _bump(label: str) -> int:
    _attempt_counts[label] = _attempt_counts.get(label, 0) + 1
    return _attempt_counts[label]


@pytest.mark.flaky(reruns=3)
def test_flaky_passes_on_third_attempt():
    threshold = _thresholds["flaky_pass_3rd"]
    attempt = _bump("flaky_pass_3rd")
    if attempt < threshold:
        raise AssertionError(f"flaky network blip on attempt {attempt}/{threshold}")
    assert True


@pytest.mark.flaky(reruns=3)
def test_flaky_exhausts_reruns():
    threshold = _thresholds["flaky_always_fails"]
    attempt = _bump("flaky_always_fails")
    if attempt < threshold:
        raise AssertionError(f"persistent failure (attempt {attempt}/{threshold})")
    assert True


@pytest.mark.flaky(reruns=1, reruns_delay=0)
def test_flaky_with_custom_reruns():
    threshold = _thresholds["flaky_custom"]
    attempt = _bump("flaky_custom")
    # reruns=1 means at most 2 attempts; threshold of 3 effectively = always fails
    if attempt < threshold:
        raise AssertionError(f"transient failure on attempt {attempt}/{threshold}")
    assert True
