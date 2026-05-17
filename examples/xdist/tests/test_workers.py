"""'Workers' module — third file so a 3+ core machine actually distributes."""

import allure
import pytest


@allure.feature("Background jobs")
@allure.story("Email sender")
@pytest.mark.parametrize("attempt", range(8))
def test_email_send_retries(attempt):
    assert attempt < 8


@allure.feature("Background jobs")
@allure.story("Cron scheduler")
def test_cron_picks_up_jobs():
    assert True


@pytest.fixture
def overloaded_queue():
    raise RuntimeError("queue worker not provisioned in dev")


@allure.feature("Background jobs")
@allure.story("Cron scheduler")
def test_cron_drains_overloaded_queue(overloaded_queue):
    # Setup-time fixture failure → status='broken'. Verifies broken status
    # also serializes correctly through xdist's worker→master report channel.
    assert overloaded_queue is not None
