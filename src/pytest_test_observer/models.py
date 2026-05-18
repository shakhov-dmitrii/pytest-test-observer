"""Shared data shapes used across the plugin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class AllureMeta(TypedDict):
    labels: dict[str, list[str]]
    links: list[tuple[str, str, str]]
    title: str
    severity: str
    allure_id: str


class CIContext(TypedDict):
    ci_provider: str
    ci_run_id: str
    git_commit: str
    git_branch: str


@dataclass(frozen=True)
class _CIProvider:
    name: str
    sentinel: str
    run_id_vars: tuple[str, ...]
    commit_vars: tuple[str, ...]
    branch_vars: tuple[str, ...]
