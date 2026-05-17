"""Realistic test suite demonstrating every plugin code path.

**Demo note:** outcomes are intentionally randomised so each run produces
different bars on the Grafana dashboard. Real test suites should be
deterministic — this is seed data for the dashboard, not a model suite.
Set DEMO_SEED to a fixed integer to make a run reproducible.
"""

import os
import random
import time

import allure
import pytest

_seed_env = os.environ.get("DEMO_SEED")
if _seed_env:
    random.seed(int(_seed_env))


@allure.epic("Account")
@allure.feature("Authentication")
@allure.story("Login")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("User logs in with valid credentials")
@allure.description("Verifies the happy path of password-based login.")
@allure.issue("https://github.com/example/issues/42", name="#42 login bug")
@pytest.mark.smoke
def test_login_with_valid_credentials():
    # Vary duration so the "slowest tests" panel has movement.
    time.sleep(random.uniform(0.01, 0.08))
    assert True


@allure.feature("Authentication")
@allure.story("Login")
@allure.severity(allure.severity_level.NORMAL)
def test_login_rejects_invalid_password():
    error = "invalid credentials"
    assert error == "invalid credentials"


@allure.feature("Authentication")
@allure.story("Signup")
@pytest.mark.parametrize(
    "email",
    [
        "alice@example.com",
        "bob@example.com",
        "missing-at-sign.example.com",
        "trailing-dot@example.",
        "weird+stuff@x.io",
        "no-tld@example",
    ],
)
def test_signup_validates_email(email):
    # Real validation — naturally splits into pass/fail by input.
    assert "@" in email and "." in email.split("@")[1] and email.split("@")[1].split(".")[-1] != ""


@allure.feature("Reports")
@allure.story("Export")
@allure.severity(allure.severity_level.MINOR)
@pytest.mark.slow
def test_dashboard_loads():
    # Variable latency — sometimes a regression, mostly fine.
    delay = random.uniform(0.02, 0.05) if random.random() > 0.15 else random.uniform(0.15, 0.30)
    time.sleep(delay)
    assert True


@allure.feature("Reports")
@allure.story("Export")
@pytest.mark.skip(reason="CSV export rewrite in progress (#117)")
def test_report_export_csv():
    pass


@allure.feature("Authentication")
@allure.story("Logout")
def test_logout_clears_session():
    # Real-world flake: ~30% of runs the session isn't cleared.
    if random.random() < 0.3:
        session = {"user_id": 1}
        raise AssertionError(f"session was not cleared: {session}")


@pytest.fixture
def admin_db():
    # Random infrastructure failure (~40%) → setup-phase error → status='broken'.
    if random.random() < 0.4:
        raise RuntimeError("admin DB connection timed out")
    return object()


@allure.feature("Admin")
@allure.severity(allure.severity_level.BLOCKER)
def test_admin_panel_access(admin_db):
    assert admin_db is not None
