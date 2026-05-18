from __future__ import annotations

import pytest

from pytest_test_observer import context
from pytest_test_observer.constants import _CI_PROVIDERS


@pytest.fixture(autouse=True)
def _clear_ci_env(monkeypatch):
    sentinel_vars = {p.sentinel for p in _CI_PROVIDERS}
    extra_vars = {
        "GITHUB_RUN_ID", "GITHUB_SHA", "GITHUB_REF_NAME", "GITHUB_HEAD_REF",
        "CI_PIPELINE_ID", "CI_COMMIT_SHA", "CI_COMMIT_REF_NAME",
        "CIRCLE_BUILD_NUM", "CIRCLE_SHA1", "CIRCLE_BRANCH",
        "BUILD_ID", "BUILD_NUMBER", "GIT_COMMIT", "GIT_BRANCH",
    }
    for var in sentinel_vars | extra_vars:
        monkeypatch.delenv(var, raising=False)


class _Completed:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.returncode = 0


def test_github_actions(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_SHA", "deadbeef")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    ctx = context.detect_ci_context()
    assert ctx == {
        "ci_provider": "github",
        "ci_run_id": "12345",
        "git_commit": "deadbeef",
        "git_branch": "main",
    }


def test_github_actions_pull_request_uses_head_ref(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/x")
    monkeypatch.setenv("GITHUB_REF_NAME", "1234/merge")
    ctx = context.detect_ci_context()
    assert ctx["git_branch"] == "feature/x"


def test_gitlab(monkeypatch):
    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.setenv("CI_PIPELINE_ID", "999")
    monkeypatch.setenv("CI_COMMIT_SHA", "abc123")
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "develop")

    ctx = context.detect_ci_context()
    assert ctx["ci_provider"] == "gitlab"
    assert ctx["ci_run_id"] == "999"
    assert ctx["git_commit"] == "abc123"
    assert ctx["git_branch"] == "develop"


def test_circle(monkeypatch):
    monkeypatch.setenv("CIRCLECI", "true")
    monkeypatch.setenv("CIRCLE_BUILD_NUM", "77")
    monkeypatch.setenv("CIRCLE_SHA1", "f00d")
    monkeypatch.setenv("CIRCLE_BRANCH", "release")

    ctx = context.detect_ci_context()
    assert ctx == {
        "ci_provider": "circle",
        "ci_run_id": "77",
        "git_commit": "f00d",
        "git_branch": "release",
    }


def test_jenkins(monkeypatch):
    monkeypatch.setenv("JENKINS_URL", "http://jenkins/")
    monkeypatch.setenv("BUILD_ID", "42")
    monkeypatch.setenv("GIT_COMMIT", "cafe")
    monkeypatch.setenv("GIT_BRANCH", "origin/main")

    ctx = context.detect_ci_context()
    assert ctx["ci_provider"] == "jenkins"
    assert ctx["ci_run_id"] == "42"


def test_local_fallback_uses_git(monkeypatch):
    captured = []

    def fake_run(args, **kwargs):
        captured.append(args)
        if "HEAD" in args and "--abbrev-ref" not in args:
            return _Completed("commit-sha\n")
        if "--abbrev-ref" in args:
            return _Completed("local-branch\n")
        return _Completed("")

    monkeypatch.setattr(context.subprocess, "run", fake_run)

    ctx = context.detect_ci_context()
    assert ctx == {
        "ci_provider": "local",
        "ci_run_id": "",
        "git_commit": "commit-sha",
        "git_branch": "local-branch",
    }


def test_is_ci_false_when_no_sentinels():
    assert context.is_ci() is False


def test_is_ci_true_with_github(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert context.is_ci() is True


def test_is_ci_true_with_gitlab(monkeypatch):
    monkeypatch.setenv("GITLAB_CI", "true")
    assert context.is_ci() is True


def test_is_ci_true_with_circle(monkeypatch):
    monkeypatch.setenv("CIRCLECI", "true")
    assert context.is_ci() is True


def test_is_ci_true_with_jenkins(monkeypatch):
    monkeypatch.setenv("JENKINS_URL", "http://jenkins/")
    assert context.is_ci() is True


def test_local_git_failure_returns_empty(git_not_installed):
    ctx = context.detect_ci_context()
    assert ctx == {
        "ci_provider": "local",
        "ci_run_id": "",
        "git_commit": "",
        "git_branch": "",
    }
