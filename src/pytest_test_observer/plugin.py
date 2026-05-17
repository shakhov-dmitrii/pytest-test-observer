from __future__ import annotations

import contextlib
import os
import threading
import uuid
import warnings
from datetime import datetime, timezone

import pytest

from pytest_test_observer import buffer
from pytest_test_observer.allure_compat import (
    detect_allure,
    empty_allure_meta,
    extract_allure_meta,
    map_status,
)
from pytest_test_observer.context import detect_ci_context, is_ci
from pytest_test_observer.helper import as_bool
from pytest_test_observer.options import add_options, resolve_options
from pytest_test_observer.reporter import ClickHouseReporter

_USER_PROP_MARKERS = "_test_observer_markers"
_USER_PROP_ALLURE = "_test_observer_allure"
_USER_PROP_TIMING = "_test_observer_timing"
_FLUSH_TIMEOUT = 10.0


def pytest_addoption(parser: pytest.Parser) -> None:
    add_options(parser)


def pytest_configure(config: pytest.Config) -> None:
    opts = resolve_options(config)
    if not opts["ch_url"]:
        return
    if str(opts.get("ch_send_from", "any")).lower() == "ci" and not is_ci():
        return
    plugin = ObserverPlugin(config, opts)
    config._test_observer = plugin
    config.pluginmanager.register(plugin, "test_observer_plugin")


def pytest_unconfigure(config: pytest.Config) -> None:
    plugin = getattr(config, "_test_observer", None)
    if plugin is not None and config.pluginmanager.is_registered(plugin):
        config.pluginmanager.unregister(plugin)
    config._test_observer = None


class ObserverPlugin:
    def __init__(self, config: pytest.Config, opts: dict) -> None:
        self.config = config
        self.opts = opts
        self.is_worker = hasattr(config, "workerinput")
        self.run_id = os.environ.get("PYTEST_OBSERVER_RUN_ID") or str(uuid.uuid4())
        self.context = detect_ci_context() if not self.is_worker else {}
        self.results: list = []
        self.allure_active = detect_allure(config.pluginmanager)

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo):
        outcome = yield
        report = outcome.get_result()
        markers = sorted({m.name for m in item.iter_markers() if not m.name.startswith("allure_")})
        report.user_properties.append((_USER_PROP_MARKERS, markers))
        report.user_properties.append((_USER_PROP_ALLURE, extract_allure_meta(item)))
        report.user_properties.append(
            (_USER_PROP_TIMING, (getattr(call, "start", None), getattr(call, "stop", None)))
        )

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if self.is_worker or not _should_record(report):
            return
        markers, allure_meta, timing = _read_user_properties(report)
        self.results.append(
            _build_row(
                report=report,
                run_id=self.run_id,
                markers=markers,
                allure_meta=allure_meta,
                timing=timing,
                context=self.context,
            )
        )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if self.is_worker or not self.results:
            return

        reporter = ClickHouseReporter(
            url=self.opts["ch_url"],
            user=self.opts["ch_user"],
            password=self.opts["ch_password"],
            db=self.opts["ch_db"],
            table=self.opts["ch_table"],
            auto_migrate=as_bool(self.opts["ch_auto_migrate"], default=True),
        )
        rows = list(self.results)
        flush_done = threading.Event()

        def _run_flush() -> None:
            try:
                reporter.flush(rows, self.run_id)
            finally:
                flush_done.set()

        thread = threading.Thread(
            target=_run_flush,
            daemon=True,
            name="test-observer-flush",
        )
        thread.start()

        if not flush_done.wait(timeout=_FLUSH_TIMEOUT) and not flush_done.is_set():
            warnings.warn(
                "[pytest-test-observer] flush thread timed out; buffering to disk",
                stacklevel=2,
            )
            with contextlib.suppress(Exception):
                buffer.write_jsonl(rows, self.run_id)


def _should_record(report: pytest.TestReport) -> bool:
    if report.when == "call":
        return True
    if report.when == "setup":
        return bool(report.failed or report.skipped)
    if report.when == "teardown":
        return bool(report.failed)
    return False


def _build_row(*, report, run_id, markers, allure_meta, timing, context) -> dict:
    started, finished = timing
    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc),
        "started_at": int(started * 1000) if started else 0,
        "finished_at": int(finished * 1000) if finished else 0,
        "nodeid": report.nodeid,
        "status": map_status(report),
        "when_phase": report.when,
        "duration": float(report.duration),
        "markers": list(markers),
        "worker_id": _worker_id(report),
        "ci_provider": context.get("ci_provider", ""),
        "ci_run_id": context.get("ci_run_id", ""),
        "git_commit": context.get("git_commit", ""),
        "git_branch": context.get("git_branch", ""),
        "allure_id": allure_meta.get("allure_id", ""),
        "allure_title": allure_meta.get("title", ""),
        "allure_severity": allure_meta.get("severity", ""),
        "allure_labels": dict(allure_meta.get("labels", {})),
        "allure_links": [tuple(link) for link in allure_meta.get("links", [])],
    }


def _read_user_properties(report: pytest.TestReport) -> tuple:
    markers: list = []
    allure_meta: dict = empty_allure_meta()
    timing: tuple = (None, None)
    for key, value in getattr(report, "user_properties", []):
        if key == _USER_PROP_MARKERS:
            markers = value
        elif key == _USER_PROP_ALLURE:
            allure_meta = value
        elif key == _USER_PROP_TIMING:
            timing = value
    return markers, allure_meta, timing


def _worker_id(report: pytest.TestReport) -> str:
    try:
        gw_id = report.node.gateway.id
    except AttributeError:
        return "master"
    return str(gw_id) if gw_id else "master"
