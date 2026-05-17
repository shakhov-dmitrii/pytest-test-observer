from __future__ import annotations

import pytest

from pytest_test_observer.reporter import parse_url


@pytest.mark.parametrize(
    "url,expected",
    [
        # Bare hostname → default port 8123, insecure
        ("clickhouse.internal", ("clickhouse.internal", 8123, False)),
        ("localhost", ("localhost", 8123, False)),
        # host:port form → explicit port, insecure
        ("localhost:8123", ("localhost", 8123, False)),
        ("ch.internal:9000", ("ch.internal", 9000, False)),
        # http://... → insecure, explicit port
        ("http://localhost:8123", ("localhost", 8123, False)),
        # http://... without port → default 8123
        ("http://ch.internal", ("ch.internal", 8123, False)),
        # https://... → secure=True, explicit port
        ("https://ch.internal:8443", ("ch.internal", 8443, True)),
        # https://... without port → default 8443 (the secure default)
        ("https://ch.internal", ("ch.internal", 8443, True)),
    ],
)
def test_parse_url_matrix(url, expected):
    assert parse_url(url) == expected
