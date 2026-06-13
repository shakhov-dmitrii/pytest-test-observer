"""Examples for the ``record_event`` fixture.

``record_event(name, payload)`` attaches a queryable diagnostic event to the
running test. Payload values must be ``str`` (cast numbers/bools yourself). When
a test fails, its events show *why* — which step broke and what state it was in.

These examples are deterministic: they always pass, so the demo suite stays
green. Swap in real logic to see events captured for genuine failures.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 1. Multi-step pipeline: record each step before its assert.
#    On failure, the earlier events are already captured, so the dashboard
#    shows exactly how far the flow got.
# ---------------------------------------------------------------------------


def _checkout(sku: str, qty: int) -> dict:
    return {"reservation": f"RSV-{sku}", "amount": qty * 10, "tracking": "TRK-123"}


def test_order_pipeline(record_event):
    order = _checkout("WIDGET-A", 2)

    record_event("inventory", {"sku": "WIDGET-A", "reservation_id": order["reservation"]})
    assert order["reservation"]

    record_event("payment", {"amount": str(order["amount"]), "ok": "true"})
    assert order["amount"] > 0

    record_event("shipment", {"tracking": order["tracking"]})
    assert order["tracking"]


# ---------------------------------------------------------------------------
# 2. Numeric metrics as strings: store numbers as str so dashboards can chart
#    avg / max / p90 over time without any schema change.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint,latency_ms", [("/users", 42), ("/orders", 88)])
def test_endpoint_latency(endpoint, latency_ms, record_event):
    budget_ms = 120
    record_event(
        "api_call",
        {
            "endpoint": endpoint,
            "latency_ms": str(latency_ms),
            "over_budget": str(latency_ms > budget_ms).lower(),
        },
    )
    assert latency_ms <= budget_ms


# ---------------------------------------------------------------------------
# 3. Context-fixture wrapper: wrap record_event to stamp a shared key (here a
#    user_id) onto every event, so steps correlate without repeating the key.
# ---------------------------------------------------------------------------


@pytest.fixture
def user_session(record_event):
    user_id = "usr-42"

    def _record(name: str, payload: dict[str, str] | None = None) -> None:
        record_event(name, {"user_id": user_id, **(payload or {})})

    return user_id, _record


def test_user_preferences(user_session):
    user_id, record = user_session

    record("login", {"ok": "true"})
    record("preference_update", {"theme": "dark", "ok": "true"})

    assert user_id == "usr-42"
