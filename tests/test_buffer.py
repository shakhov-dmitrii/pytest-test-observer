from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from pytest_test_observer import buffer

# Apply the `xdg_cache_home` fixture (defined in conftest.py) to every test in this file.
pytestmark = pytest.mark.usefixtures("xdg_cache_home")


def test_write_jsonl_round_trip(tmp_path):
    rows = [
        {
            "run_id": "abc",
            "timestamp": datetime(2025, 1, 2, 3, 4, 5, 678000, tzinfo=timezone.utc),
            "nodeid": "tests/test_x.py::test_a",
            "status": "passed",
            "markers": ["slow", "smoke"],
            "allure_labels": {"feature": ["Auth"], "tag": ["smoke"]},
            "allure_links": [("issue", "https://x/1", "Bug")],
        }
    ]

    path = buffer.write_jsonl(rows, "run-42")
    assert path == tmp_path / "pytest-test-observer" / "run-42.jsonl"
    assert path.exists()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])

    assert parsed["run_id"] == "abc"
    assert parsed["timestamp"] == "2025-01-02T03:04:05.678+00:00"
    assert parsed["markers"] == ["slow", "smoke"]
    assert parsed["allure_labels"] == {"feature": ["Auth"], "tag": ["smoke"]}
    assert parsed["allure_links"] == [["issue", "https://x/1", "Bug"]]


def test_write_jsonl_appends():
    buffer.write_jsonl([{"k": 1}], "run-x")
    path = buffer.write_jsonl([{"k": 2}], "run-x")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["k"] for line in lines] == [1, 2]


def test_write_jsonl_creates_parent_dirs(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "nest"
    monkeypatch.setenv("XDG_CACHE_HOME", str(nested))

    path = buffer.write_jsonl([{"a": "b"}], "run-nest")
    assert path.exists()
    assert path.parent == nested / "pytest-test-observer"


def test_write_jsonl_sanitises_path_traversal(tmp_path):
    path = buffer.write_jsonl([{"k": 1}], "../../etc/evil")

    assert path.parent == tmp_path / "pytest-test-observer"
    assert path.name == ".._.._etc_evil.jsonl"
    assert path.exists()


def test_write_jsonl_truncates_overly_long_run_id():
    long_id = "a" * 500
    path = buffer.write_jsonl([{"k": 1}], long_id)

    assert len(path.stem) == 128
    assert path.exists()


def test_write_jsonl_empty_run_id_falls_back():
    path = buffer.write_jsonl([{"k": 1}], "")
    assert path.name == "unknown.jsonl"
    assert path.exists()


def test_write_jsonl_run_id_only_unsafe_chars():
    path = buffer.write_jsonl([{"k": 1}], "////")
    assert path.name == "____.jsonl"


def test_write_jsonl_empty_rows_does_not_create_file():
    path = buffer.write_jsonl([], "empty-run")
    assert path.parent.exists()
    assert not path.exists()


def test_json_default_raises_on_unsupported_type():
    with pytest.raises(TypeError, match="not JSON serializable"):
        buffer._json_default({1, 2, 3})


def test_json_default_serializes_datetime():
    result = buffer._json_default(datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc))
    assert result == "2026-05-11T12:00:00.000+00:00"


def test_json_default_serializes_tuple_as_list():
    assert buffer._json_default(("a", "b", "c")) == ["a", "b", "c"]
