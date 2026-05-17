"""'API' module — runs on whichever xdist worker pulls it via loadscope."""

import allure
import pytest


@allure.feature("API")
@allure.story("Authentication")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_api_login():
    assert True


@allure.feature("API")
@allure.story("Authentication")
def test_api_token_refresh():
    assert True


@allure.feature("API")
@allure.story("Users")
@pytest.mark.parametrize("user_id", [1, 2, 3, 4, 5])
def test_api_get_user(user_id):
    assert user_id > 0


@allure.feature("API")
@allure.story("Users")
def test_api_create_user_invalid_email():
    # Intentional failure to show how a real failure shows up under xdist.
    raise AssertionError("API returned 500 instead of 400 for invalid email")
