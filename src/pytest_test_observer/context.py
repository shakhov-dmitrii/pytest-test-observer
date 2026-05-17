"""Detect CI provider context and read git commit/branch for the current run."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping

from pytest_test_observer.constants import _CI_PROVIDERS
from pytest_test_observer.models import CIContext


def is_ci() -> bool:
    env = os.environ
    return any(env.get(p.sentinel) for p in _CI_PROVIDERS)


def detect_ci_context() -> CIContext:
    env = os.environ
    for provider in _CI_PROVIDERS:
        if env.get(provider.sentinel):
            return {
                "ci_provider": provider.name,
                "ci_run_id": _first_env(env, provider.run_id_vars),
                "git_commit": _first_env(env, provider.commit_vars),
                "git_branch": _first_env(env, provider.branch_vars),
            }
    commit, branch = _git_local()
    return {
        "ci_provider": "local",
        "ci_run_id": "",
        "git_commit": commit,
        "git_branch": branch,
    }


def _first_env(env: Mapping[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = env.get(name, "")
        if value:
            return value
    return ""


def _git_local() -> tuple[str, str]:
    return (
        _run_git(["rev-parse", "HEAD"]),
        _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
    )


def _run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""
