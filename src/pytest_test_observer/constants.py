from enum import StrEnum

from pytest_test_observer.models import _CIProvider


class TestStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BROKEN = "broken"
    SKIPPED = "skipped"
    RERUN = "rerun"
    UNKNOWN = "unknown"


_CI_PROVIDERS: tuple[_CIProvider, ...] = (
    _CIProvider(
        name="github",
        sentinel="GITHUB_ACTIONS",
        run_id_vars=("GITHUB_RUN_ID",),
        commit_vars=("GITHUB_SHA",),
        branch_vars=("GITHUB_HEAD_REF", "GITHUB_REF_NAME"),
    ),
    _CIProvider(
        name="gitlab",
        sentinel="GITLAB_CI",
        run_id_vars=("CI_PIPELINE_ID",),
        commit_vars=("CI_COMMIT_SHA",),
        branch_vars=("CI_COMMIT_REF_NAME",),
    ),
    _CIProvider(
        name="circle",
        sentinel="CIRCLECI",
        run_id_vars=("CIRCLE_BUILD_NUM",),
        commit_vars=("CIRCLE_SHA1",),
        branch_vars=("CIRCLE_BRANCH",),
    ),
    _CIProvider(
        name="jenkins",
        sentinel="JENKINS_URL",
        run_id_vars=("BUILD_ID", "BUILD_NUMBER"),
        commit_vars=("GIT_COMMIT",),
        branch_vars=("GIT_BRANCH",),
    ),
)


LABEL_MARK = "allure_label"
LINK_MARK = "allure_link"

LABEL_TYPE_KEY = "label_type"
LINK_TYPE_KEY = "link_type"
LINK_NAME_KEY = "name"

SEVERITY_LABEL = "severity"
ID_LABEL = "as_id"  # LabelType.ID resolves to "as_id" in allure-python-commons

DISPLAY_NAME_ATTR = "__allure_display_name__"
