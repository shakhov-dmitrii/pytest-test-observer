"""Driver for the load test.

Runs the parametrized suite twice: once with the plugin inert (baseline),
once with --ch-url pointing at a local ClickHouse. Reports wall-clock and
peak RSS for each, then queries the resulting table to verify the row count
and status distribution match expectations.

    uv run python loadtest/run_loadtest.py
    LOADTEST_COUNT=5000 uv run python loadtest/run_loadtest.py
"""

from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

CH_CONTAINER = "pytest-test-observer-clickhouse"
CH_HTTP = "http://localhost:8123"


def _peak_rss_mib() -> float:
    val = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return val / (1024 * 1024) if sys.platform == "darwin" else val / 1024


def _human_bytes(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TiB"


def _run(label: str, args: list, env: dict | None = None, metrics_path: str | None = None) -> int:
    print(f"\n=== {label} ===", flush=True)
    print(f"$ uv run pytest {' '.join(args)}", flush=True)
    full_env = {**os.environ, **(env or {})}
    if metrics_path:
        full_env["PYTEST_OBSERVER_METRICS_FILE"] = metrics_path
        # ensure stale data isn't reused
        if os.path.exists(metrics_path):
            os.remove(metrics_path)
    rss_before = _peak_rss_mib()
    start = time.perf_counter()
    proc = subprocess.run(["uv", "run", "pytest", *args], env=full_env)
    elapsed = time.perf_counter() - start
    rss_after = _peak_rss_mib()
    peak_delta = max(rss_after - rss_before, rss_after)
    print(
        f"  exit={proc.returncode}  elapsed={elapsed:.2f}s  peak_rss_for_run≈{peak_delta:.1f} MiB"
    )
    if metrics_path and os.path.exists(metrics_path):
        with open(metrics_path) as f:
            m = json.load(f)
        rows = m.get("rows", 0)
        flush_s = m.get("flush_seconds", 0.0)
        bytes_w = m.get("bytes_written", 0)
        rps = (rows / flush_s) if flush_s > 0 else 0
        bps = (bytes_w / flush_s) if flush_s > 0 else 0
        print(
            f"  flush:  rows={rows}  data={_human_bytes(bytes_w)}  "
            f"duration={flush_s:.3f}s  ({rps:,.0f} rows/s, {_human_bytes(bps)}/s)"
        )
    return proc.returncode


def _ch_query(sql: str) -> str:
    return subprocess.check_output(
        ["docker", "exec", CH_CONTAINER, "clickhouse-client", "-q", sql],
        text=True,
    ).strip()


def _verify_clickhouse(table: str, expect_xdist: bool = False) -> None:
    print(f"\n--- ClickHouse: default.{table} ---", flush=True)
    if not shutil.which("docker"):
        print("  docker not on PATH; skipping verification")
        return

    try:
        from loadtest.test_load import expected_counts
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from loadtest.test_load import expected_counts

    expected = expected_counts()
    expected_total = sum(expected.values())

    actual_total = int(_ch_query(f"SELECT count() FROM default.{table}"))
    print(f"  rows in ClickHouse: {actual_total} (expected {expected_total})")

    distribution = _ch_query(
        f"SELECT status, count() AS n FROM default.{table} "
        f"GROUP BY status ORDER BY n DESC FORMAT TSV"
    )
    actual = {}
    print("  status distribution:")
    for line in distribution.splitlines():
        status, n = line.split("\t")
        actual[status] = int(n)
        marker = "OK" if actual[status] == expected.get(status, 0) else "MISMATCH"
        print(f"    {status:<10} {n:>8}  (expected {expected.get(status, 0)})  [{marker}]")

    worker_ids = _ch_query(
        f"SELECT worker_id, count() FROM default.{table} "
        f"GROUP BY worker_id ORDER BY worker_id FORMAT TSV"
    )
    print("  worker_id distribution:")
    worker_id_set = set()
    for line in worker_ids.splitlines():
        wid, n = line.split("\t")
        worker_id_set.add(wid)
        print(f"    {wid:<10} {n:>8}")

    counts_ok = actual == expected and actual_total == expected_total
    if expect_xdist:
        xdist_ok = bool(worker_id_set) and all(w.startswith("gw") for w in worker_id_set)
        if counts_ok and xdist_ok:
            print(f"  PASS: counts match and {len(worker_id_set)} xdist workers visible.")
        else:
            print(
                f"  FAIL: counts_ok={counts_ok}, "
                f"all_worker_ids_are_gw*={xdist_ok}, worker_ids={sorted(worker_id_set)}"
            )
    else:
        if counts_ok and worker_id_set == {"master"}:
            print("  PASS: counts match and only 'master' wrote (single-process).")
        else:
            print(
                f"  FAIL: counts_ok={counts_ok}, worker_ids={sorted(worker_id_set)} "
                "(expected only 'master')"
            )


def main() -> None:
    count = os.environ.get("LOADTEST_COUNT", "20000")
    workers = int(os.environ.get("LOADTEST_XDIST_WORKERS", "4"))
    table_single = f"loadtest_{uuid.uuid4().hex[:8]}"
    table_xdist = f"loadtest_xdist_{uuid.uuid4().hex[:8]}"
    common = [
        "loadtest/test_load.py",
        "-q",
        "--no-header",
        "--tb=no",
        "-p",
        "no:cacheprovider",
    ]
    print(f"LOADTEST_COUNT={count}, xdist_workers={workers}", flush=True)

    with tempfile.TemporaryDirectory(prefix="pytest-observer-loadtest-") as tmp:
        m_single = os.path.join(tmp, "single.json")
        m_xdist = os.path.join(tmp, "xdist.json")

        print("\n[1/3] baseline (plugin inert, no --ch-url) — measures pytest overhead alone")
        _run("baseline", common)

        print("\n[2/3] with ClickHouse, single-process")
        _run(
            "with-clickhouse",
            [*common, "--ch-url=localhost:8123", f"--ch-table={table_single}"],
            metrics_path=m_single,
        )
        _verify_clickhouse(table_single, expect_xdist=False)

        print(f"\n[3/3] with ClickHouse + xdist (-n {workers}) — worker→master serialization")
        _run(
            "with-clickhouse-xdist",
            [*common, "-n", str(workers), "--ch-url=localhost:8123", f"--ch-table={table_xdist}"],
            metrics_path=m_xdist,
        )
        _verify_clickhouse(table_xdist, expect_xdist=True)


if __name__ == "__main__":
    main()
