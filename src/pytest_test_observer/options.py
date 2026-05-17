"""CLI / env-var / pyproject.toml-ini option registration and resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


# (cli_name, ini_name, env_var, default)
OPTION_SPECS: tuple[tuple[str, str, str, str | None], ...] = (
    ("--ch-url", "ch_url", "PYTEST_OBSERVER_CH_URL", None),
    ("--ch-user", "ch_user", "PYTEST_OBSERVER_CH_USER", "default"),
    ("--ch-password", "ch_password", "PYTEST_OBSERVER_CH_PASSWORD", ""),
    ("--ch-db", "ch_db", "PYTEST_OBSERVER_CH_DB", "default"),
    ("--ch-table", "ch_table", "PYTEST_OBSERVER_CH_TABLE", "pytest_results"),
    ("--ch-send-from", "ch_send_from", "PYTEST_OBSERVER_CH_SEND_FROM", "any"),
    ("--ch-auto-migrate", "ch_auto_migrate", "PYTEST_OBSERVER_CH_AUTO_MIGRATE", "true"),
)

_HELP: dict[str, str] = {
    "ch_url": "ClickHouse URL (host, host:port, or http(s)://host:port).",
    "ch_user": "ClickHouse username.",
    "ch_password": "ClickHouse password.",
    "ch_db": "ClickHouse database name.",
    "ch_table": "ClickHouse table name.",
    "ch_send_from": "When to send: 'any' (default: local + CI) or 'ci' (skip when no CI env detected).",
    "ch_auto_migrate": "Auto-add missing columns via ALTER TABLE when the schema drifts forward. true/false (default true).",
}


def add_options(parser: pytest.Parser) -> None:
    group = parser.getgroup("test-observer")
    for cli, ini, env, _default in OPTION_SPECS:
        group.addoption(
            cli,
            action="store",
            default=None,
            help=f"{_HELP[ini]} Also: env {env} or `{ini}` in pyproject.toml [tool.pytest.ini_options].",
        )
        parser.addini(ini, _HELP[ini], default=None)


def resolve_options(config: pytest.Config) -> dict[str, str | None]:
    return {
        ini: _resolve_one(config, cli, ini, env, default) for cli, ini, env, default in OPTION_SPECS
    }


def _resolve_one(
    config: pytest.Config,
    cli: str,
    ini: str,
    env: str,
    default: str | None,
) -> str | None:
    cli_value = config.getoption(cli)
    if cli_value is not None:
        return cli_value
    env_value = os.environ.get(env)
    if env_value is not None:
        return env_value
    ini_value = config.getini(ini)
    if ini_value:
        return ini_value
    return default
