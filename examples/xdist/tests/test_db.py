"""'DB' module — typically lands on a different worker than test_api.py
under the default `--dist=loadscope`."""

import allure
import pytest


@allure.feature("Database")
@allure.story("Connection pool")
@pytest.mark.smoke
def test_db_connect():
    assert True


@allure.feature("Database")
@allure.story("Migrations")
@allure.severity(allure.severity_level.BLOCKER)
def test_db_migration_idempotent():
    assert True


@allure.feature("Database")
@allure.story("Queries")
@pytest.mark.parametrize("table", ["users", "orders", "products", "audit_log"])
def test_db_table_exists(table):
    assert table in ("users", "orders", "products", "audit_log")


@allure.feature("Database")
@allure.story("Queries")
@pytest.mark.skip(reason="rewriting after the schema split (#220)")
def test_db_legacy_query():
    pass
