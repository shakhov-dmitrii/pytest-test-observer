from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from pytest_test_observer import reporter as reporter_module
from pytest_test_observer.plugin import _build_row, _should_record, _worker_id

# Plugin tests share the buffer-and-run-id isolation fixture from conftest.py.
pytestmark = pytest.mark.usefixtures("isolate_buffer_and_run_id")


def test_plugin_inert_without_ch_url(pytester, fake_clients):
    pytester.makepyfile(
        """
        def test_pass():
            assert True
        """
    )
    result = pytester.runpytest_inprocess()
    result.assert_outcomes(passed=1)
    assert fake_clients == []


def test_records_results_with_markers_and_allure(pytester, fake_clients):
    pytester.makepyfile(
        """
        import allure
        import pytest

        @pytest.mark.slow
        @allure.feature("Auth")
        @allure.severity(allure.severity_level.CRITICAL)
        @allure.title("Login flow")
        def test_pass():
            assert True

        def test_fail():
            raise ValueError("boom")

        @pytest.mark.skip
        def test_skip():
            pass
        """
    )
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-table=t",
    )
    result.assert_outcomes(passed=1, failed=1, skipped=1)

    assert len(fake_clients) == 1
    inserts = fake_clients[0].inserts
    assert len(inserts) == 1
    table, data, column_names = inserts[0]
    assert table == "t"

    rows_by_status = {row[column_names.index("status")]: row for row in data}
    assert set(rows_by_status) == {"passed", "failed", "skipped"}

    passed = rows_by_status["passed"]
    assert "slow" in passed[column_names.index("markers")]
    assert passed[column_names.index("allure_labels")] == {
        "feature": ["Auth"],
        "severity": ["critical"],
    }
    assert passed[column_names.index("allure_severity")] == "critical"
    assert passed[column_names.index("allure_title")] == "Login flow"

    failed = rows_by_status["failed"]
    assert failed[column_names.index("when_phase")] == "call"

    for row in data:
        assert row[column_names.index("run_id")] == "test-run-1"
        started = row[column_names.index("started_at")]
        finished = row[column_names.index("finished_at")]
        assert isinstance(started, int) and isinstance(finished, int)
        assert started > 0
        assert finished >= started


def test_successful_flush_does_not_create_jsonl_fallback(pytester, fake_clients, tmp_path):
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-table=t",
    )
    result.assert_outcomes(passed=1)

    assert len(fake_clients) == 1
    assert len(fake_clients[0].inserts) == 1

    buffer_path = tmp_path / "cache" / "pytest-test-observer" / "test-run-1.jsonl"
    assert not buffer_path.exists(), (
        f"unexpected JSONL fallback at {buffer_path}; "
        "flush thread succeeded but main thread also wrote — race not closed"
    )


def test_clickhouse_failure_falls_back_to_jsonl(pytester, monkeypatch, tmp_path):
    def boom_factory(**kwargs):
        raise ConnectionError("clickhouse down")

    monkeypatch.setattr(reporter_module.clickhouse_connect, "get_client", boom_factory)

    pytester.makepyfile(
        """
        def test_a():
            assert True

        def test_b():
            assert True
        """
    )
    result = pytester.runpytest_inprocess("--ch-url=localhost:8123")
    assert result.ret == 0

    buffer_path = tmp_path / "cache" / "pytest-test-observer" / "test-run-1.jsonl"
    assert buffer_path.exists(), f"expected {buffer_path} to exist"

    lines = buffer_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert {row["nodeid"].rsplit("::", 1)[-1] for row in parsed} == {"test_a", "test_b"}
    assert all(row["run_id"] == "test-run-1" for row in parsed)
    assert all(row["status"] == "passed" for row in parsed)


def test_config_from_pytest_ini(pytester, fake_clients):
    pytester.makefile(
        ".ini",
        pytest="""
            [pytest]
            ch_url = localhost:8123
            ch_table = from_ini_table
            """,
    )
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess()
    result.assert_outcomes(passed=1)
    assert len(fake_clients) == 1
    table, _, _ = fake_clients[0].inserts[0]
    assert table == "from_ini_table"


def test_config_from_env_var(pytester, fake_clients, monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CH_URL", "localhost:8123")
    monkeypatch.setenv("PYTEST_OBSERVER_CH_TABLE", "from_env_table")
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess()
    result.assert_outcomes(passed=1)
    assert len(fake_clients) == 1
    table, _, _ = fake_clients[0].inserts[0]
    assert table == "from_env_table"


def test_cli_overrides_env(pytester, fake_clients, monkeypatch):
    monkeypatch.setenv("PYTEST_OBSERVER_CH_URL", "localhost:8123")
    monkeypatch.setenv("PYTEST_OBSERVER_CH_TABLE", "env_table")
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess("--ch-table=cli_table")
    result.assert_outcomes(passed=1)
    table, _, _ = fake_clients[0].inserts[0]
    assert table == "cli_table"


def test_send_from_ci_skips_when_not_in_ci(pytester, fake_clients, monkeypatch):
    from pytest_test_observer.constants import _CI_PROVIDERS
    for p in _CI_PROVIDERS:
        monkeypatch.delenv(p.sentinel, raising=False)
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-send-from=ci",
    )
    result.assert_outcomes(passed=1)
    assert fake_clients == [], "plugin should be inert outside CI when send_from=ci"


def test_send_from_ci_sends_when_in_ci(pytester, fake_clients, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-send-from=ci",
        "--ch-table=ci_only",
    )
    result.assert_outcomes(passed=1)
    assert len(fake_clients) == 1
    table, _, _ = fake_clients[0].inserts[0]
    assert table == "ci_only"


def test_send_from_any_sends_locally(pytester, fake_clients):
    pytester.makepyfile("def test_one(): assert True")
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-send-from=any",
    )
    result.assert_outcomes(passed=1)
    assert len(fake_clients) == 1


def test_async_tests_record_to_clickhouse(pytester, fake_clients):
    pytest.importorskip("pytest_asyncio")

    pytester.makepyfile(
        """
        import asyncio
        import allure
        import pytest

        @pytest.mark.asyncio
        @pytest.mark.smoke
        @allure.feature("Async API")
        @allure.severity(allure.severity_level.CRITICAL)
        async def test_async_pass():
            await asyncio.sleep(0.01)
            assert True

        @pytest.mark.asyncio
        async def test_async_fail():
            await asyncio.sleep(0)
            raise ValueError("async boom")
        """
    )
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-table=async_t",
    )
    result.assert_outcomes(passed=1, failed=1)

    assert len(fake_clients) == 1
    inserts = fake_clients[0].inserts
    assert len(inserts) == 1
    table, data, column_names = inserts[0]
    assert table == "async_t"

    rows_by_status = {row[column_names.index("status")]: row for row in data}
    assert set(rows_by_status) == {"passed", "failed"}

    passed = rows_by_status["passed"]
    assert "smoke" in passed[column_names.index("markers")]
    assert passed[column_names.index("allure_labels")] == {
        "feature": ["Async API"],
        "severity": ["critical"],
    }
    assert passed[column_names.index("allure_severity")] == "critical"

    started = passed[column_names.index("started_at")]
    finished = passed[column_names.index("finished_at")]
    assert isinstance(started, int) and started > 0
    assert finished >= started
    assert passed[column_names.index("duration")] >= 0.01


def test_xdist_aggregates_on_master_without_duplicates(xdist_test_suite, fake_clients):
    pytester = xdist_test_suite
    result = pytester.runpytest_subprocess(
        "--ch-url=localhost:8123",
        "--ch-table=xdist_t",
        "-n",
        "2",
        "-p",
        "no:cacheprovider",
    )
    result.assert_outcomes(passed=2, failed=1, skipped=1)


def test_xdist_in_process_records_via_master(xdist_test_suite, fake_clients):
    pytester = xdist_test_suite
    result = pytester.runpytest_inprocess(
        "--ch-url=localhost:8123",
        "--ch-table=xdist_t",
        "-n",
        "2",
    )
    result.assert_outcomes(passed=2, failed=1, skipped=1)

    assert len(fake_clients) == 1, (
        f"expected exactly one ClickHouse client (master only); got {len(fake_clients)}"
    )

    inserts = fake_clients[0].inserts
    assert len(inserts) == 1
    table, data, column_names = inserts[0]
    assert table == "xdist_t"
    assert len(data) == 4, f"expected 4 rows (no dupes / no missing), got {len(data)}"

    nodeid_idx = column_names.index("nodeid")
    status_idx = column_names.index("status")
    worker_idx = column_names.index("worker_id")

    by_nodeid = {row[nodeid_idx].rsplit("::", 1)[-1]: row for row in data}
    assert set(by_nodeid) == {"test_a", "test_b", "test_c", "test_d"}
    assert by_nodeid["test_a"][status_idx] == "passed"
    assert by_nodeid["test_b"][status_idx] == "passed"
    assert by_nodeid["test_c"][status_idx] == "failed"
    assert by_nodeid["test_d"][status_idx] == "skipped"

    worker_ids = {row[worker_idx] for row in data}
    assert all(wid.startswith("gw") for wid in worker_ids), (
        f"expected gw* worker ids from xdist, got {worker_ids}"
    )


def test_worker_id_master_fallback():
    class Report:
        nodeid = "x"

    assert _worker_id(Report()) == "master"


def test_worker_id_from_xdist_gateway():
    class Gateway:
        id = "gw0"

    class Node:
        gateway = Gateway()

    class Report:
        node = Node()

    assert _worker_id(Report()) == "gw0"


@pytest.mark.parametrize(
    "when,failed,skipped,expected",
    [
        # call phase: always recorded
        ("call", False, False, True),
        ("call", True, False, True),
        ("call", False, True, True),
        # setup phase: recorded only when failed (broken) or skipped
        ("setup", False, False, False),  # passing setup → skipped
        ("setup", True, False, True),  # broken setup
        ("setup", False, True, True),  # @pytest.mark.skip detected in setup
        # teardown phase: recorded only when failed
        ("teardown", False, False, False),
        ("teardown", True, False, True),
        ("teardown", False, True, False),
        # unrecognised phases never recorded
        ("collect", False, False, False),
        ("", False, False, False),
    ],
)
def test_should_record_matrix(when, failed, skipped, expected):
    report = SimpleNamespace(when=when, failed=failed, skipped=skipped)
    assert _should_record(report) is expected


def _fake_call_report(**overrides):
    base = dict(
        nodeid="tests/test_x.py::test_y",
        when="call",
        duration=0.05,
        passed=True,
        failed=False,
        skipped=False,
        outcome="passed",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _full_allure_meta():
    return {
        "labels": {"feature": ["Auth"], "tag": ["smoke"]},
        "links": [("issue", "https://x/1", "Bug 1")],
        "title": "User login",
        "severity": "critical",
        "allure_id": "TC-101",
    }


def _full_context():
    return {
        "ci_provider": "github",
        "ci_run_id": "12345",
        "git_commit": "deadbeef",
        "git_branch": "main",
    }


def test_build_row_assembles_every_field():
    row = _build_row(
        report=_fake_call_report(),
        run_id="run-1",
        markers=["smoke", "slow"],
        allure_meta=_full_allure_meta(),
        timing=(1000.500, 1000.575),
        context=_full_context(),
    )

    assert row["run_id"] == "run-1"
    assert row["nodeid"] == "tests/test_x.py::test_y"
    assert row["status"] == "passed"
    assert row["when_phase"] == "call"
    assert row["duration"] == 0.05
    assert row["markers"] == ["smoke", "slow"]
    assert row["worker_id"] == "master"
    assert row["started_at"] == 1000500
    assert row["finished_at"] == 1000575
    assert row["allure_severity"] == "critical"
    assert row["allure_id"] == "TC-101"
    assert row["allure_title"] == "User login"
    assert row["allure_labels"] == {"feature": ["Auth"], "tag": ["smoke"]}
    assert row["allure_links"] == [("issue", "https://x/1", "Bug 1")]
    assert row["ci_provider"] == "github"
    assert row["git_commit"] == "deadbeef"


def test_build_row_handles_missing_timing():
    row = _build_row(
        report=_fake_call_report(),
        run_id="r",
        markers=[],
        allure_meta=_full_allure_meta(),
        timing=(None, None),
        context=_full_context(),
    )
    assert row["started_at"] == 0
    assert row["finished_at"] == 0


def test_build_row_empty_allure_meta_keeps_field_shape():
    empty_meta = {
        "labels": {},
        "links": [],
        "title": "",
        "severity": "",
        "allure_id": "",
    }
    row = _build_row(
        report=_fake_call_report(),
        run_id="r",
        markers=[],
        allure_meta=empty_meta,
        timing=(1.0, 2.0),
        context={},
    )
    assert row["allure_labels"] == {}
    assert row["allure_links"] == []
    assert row["allure_severity"] == ""
    assert row["allure_title"] == ""
    assert row["ci_provider"] == ""
    assert row["git_commit"] == ""
