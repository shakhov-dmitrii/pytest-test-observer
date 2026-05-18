from __future__ import annotations

import pytest

from pytest_test_observer import replay
from pytest_test_observer.schema import COLUMNS

# All replay tests want XDG_CACHE_HOME pinned to tmp_path.
pytestmark = pytest.mark.usefixtures("xdg_cache_home")


def test_parse_jsonl_text_round_trips_rows():
    text = '{"run_id": "r1", "nodeid": "t1"}\n{"run_id": "r1", "nodeid": "t2"}\n'
    rows, skipped = replay.parse_jsonl_text(text)
    assert skipped == 0
    assert len(rows) == 2
    assert rows[0]["nodeid"] == "t1"
    assert rows[1]["nodeid"] == "t2"


def test_parse_jsonl_text_fills_missing_columns_with_defaults():
    text = '{"nodeid": "old-style-row"}\n'
    rows, _ = replay.parse_jsonl_text(text)
    assert len(rows) == 1
    row = rows[0]
    for col in COLUMNS:
        assert col in row
    assert row["duration"] == 0.0
    assert row["started_at"] == 0
    assert row["markers"] == []
    assert row["allure_labels"] == {}


def test_parse_jsonl_text_skips_malformed_lines(recwarn):
    text = '{"nodeid": "good"}\nnot json at all\n\n{"nodeid": "also-good"}\n'
    rows, skipped = replay.parse_jsonl_text(text)
    assert len(rows) == 2
    assert skipped == 1
    assert any("not valid JSON" in str(w.message) for w in recwarn)


def test_parse_jsonl_text_skips_non_object_top_level(recwarn):
    text = '[1, 2, 3]\n{"nodeid": "ok"}\n'
    rows, skipped = replay.parse_jsonl_text(text)
    assert len(rows) == 1
    assert skipped == 1
    assert any("not a JSON object" in str(w.message) for w in recwarn)


def test_find_buffer_files_scans_default_dir_when_no_paths(tmp_path):
    buf = tmp_path / "pytest-test-observer"
    buf.mkdir()
    (buf / "run-a.jsonl").write_text("{}\n")
    (buf / "run-b.jsonl").write_text("{}\n")
    (buf / "ignored.txt").write_text("not jsonl")

    found = replay.find_buffer_files([])
    assert {p.name for p in found} == {"run-a.jsonl", "run-b.jsonl"}


def test_find_buffer_files_expands_directories(tmp_path):
    sub = tmp_path / "buffers"
    sub.mkdir()
    (sub / "a.jsonl").write_text("{}")
    (sub / "b.jsonl").write_text("{}")
    found = replay.find_buffer_files([sub])
    assert sorted(p.name for p in found) == ["a.jsonl", "b.jsonl"]


def test_find_buffer_files_accepts_explicit_files(tmp_path):
    f = tmp_path / "explicit.jsonl"
    f.write_text("{}")
    found = replay.find_buffer_files([f])
    assert found == [f]


def test_find_buffer_files_warns_on_missing_path(tmp_path, recwarn):
    found = replay.find_buffer_files([tmp_path / "does-not-exist.jsonl"])
    assert found == []
    assert any("no such file" in str(w.message) for w in recwarn)


class _SuccessfulReporter:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list = []

    def flush(self, rows, run_id):
        self.calls.append((list(rows), run_id))
        return self.ok


def test_replay_file_deletes_buffer_on_successful_flush(tmp_path):
    f = tmp_path / "run-1.jsonl"
    f.write_text('{"nodeid": "t1"}\n{"nodeid": "t2"}\n')
    reporter = _SuccessfulReporter(ok=True)

    rows, skipped, ok = replay.replay_file(reporter, f, keep=False)

    assert rows == 2
    assert skipped == 0
    assert ok is True
    assert not f.exists()
    assert len(reporter.calls) == 1
    flushed_rows, run_id = reporter.calls[0]
    assert run_id == "run-1"
    assert {r["nodeid"] for r in flushed_rows} == {"t1", "t2"}


def test_replay_file_keep_flag_preserves_buffer(tmp_path):
    f = tmp_path / "run-keep.jsonl"
    f.write_text('{"nodeid": "t1"}\n')
    reporter = _SuccessfulReporter(ok=True)

    rows, _, ok = replay.replay_file(reporter, f, keep=True)
    assert rows == 1
    assert ok is True
    assert f.exists()


def test_replay_file_returns_false_when_flush_fails(tmp_path):
    f = tmp_path / "run-fail.jsonl"
    f.write_text('{"nodeid": "t1"}\n')
    reporter = _SuccessfulReporter(ok=False)

    rows, _, ok = replay.replay_file(reporter, f, keep=False)
    assert rows == 1
    assert ok is False
    assert not f.exists()


def test_replay_file_empty_returns_no_op(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    reporter = _SuccessfulReporter(ok=True)

    rows, skipped, ok = replay.replay_file(reporter, f, keep=False)
    assert rows == 0
    assert skipped == 0
    assert ok is True
    assert reporter.calls == []


def test_main_dry_run_lists_without_calling_reporter(tmp_path, capsys, monkeypatch):
    buf = tmp_path / "pytest-test-observer"
    buf.mkdir()
    (buf / "run-x.jsonl").write_text('{"nodeid": "t"}\n')

    called = []

    class Boom:
        def __init__(self, *a, **kw):
            called.append("constructed")
            raise RuntimeError("should not be reached")

    monkeypatch.setattr(replay, "ClickHouseReporter", Boom)

    rc = replay.main(["--dry-run"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "run-x.jsonl" in out
    assert "would replay" in out
    assert called == []


def test_main_no_files_returns_zero(capsys):
    rc = replay.main([])
    assert rc == 0
    assert "no buffer files found" in capsys.readouterr().err


def test_main_requires_ch_url_when_files_exist(tmp_path, capsys):
    buf = tmp_path / "pytest-test-observer"
    buf.mkdir()
    (buf / "x.jsonl").write_text('{"nodeid": "t"}\n')

    rc = replay.main([])
    assert rc == 2
    assert "--ch-url is required" in capsys.readouterr().err


def test_main_runs_reporter_and_returns_zero_on_success(tmp_path, capsys, monkeypatch):
    buf = tmp_path / "pytest-test-observer"
    buf.mkdir()
    (buf / "run-1.jsonl").write_text('{"nodeid": "a"}\n{"nodeid": "b"}\n')

    monkeypatch.setattr(replay, "ClickHouseReporter", lambda **kw: _SuccessfulReporter(ok=True))

    rc = replay.main(["--ch-url=localhost:8123"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "2 rows" in out
    assert "0 files failed" in out


def test_main_returns_one_when_a_file_fails(tmp_path, capsys, monkeypatch):
    buf = tmp_path / "pytest-test-observer"
    buf.mkdir()
    (buf / "run-fail.jsonl").write_text('{"nodeid": "t"}\n')

    monkeypatch.setattr(replay, "ClickHouseReporter", lambda **kw: _SuccessfulReporter(ok=False))

    rc = replay.main(["--ch-url=localhost:8123"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "FAILED" in out
    assert "1 files failed" in out
