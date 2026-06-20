"""
test_tracking.py — Unit + endpoint tests for the tracking service.

The LLM, Redis state store, backend, and delivery clients are all mocked, so
no real network or Redis is touched.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core import maps_client
from app.main import app
from app.services import orchestrator, tracking_service
from app.tests.helpers import FakeLLM, auth_header, text_completion

client = TestClient(app)

ADDR = "12 Park St, Pune, Maharashtra, 411001, IN"


# ── Mock maps client ───────────────────────────────────────────────────────

def test_mock_route_is_deterministic():
    r1 = maps_client.get_route(ADDR)
    r2 = maps_client.get_route(ADDR)
    assert r1.distance_km == r2.distance_km
    assert r1.destination == r2.destination
    assert r1.distance_km > 0


# ── tracking_service stage ordering ────────────────────────────────────────

def test_stage_ordering():
    assert tracking_service.next_stage("pending") == "dispatched"
    assert tracking_service.next_stage("out_for_delivery") == "delivered"
    assert tracking_service.next_stage("delivered") is None


def test_start_tracking_creates_pending_checkpoint(_memory_state_store):
    state = tracking_service.start_tracking("o1", ADDR)
    assert state["status"] == "pending"
    assert state["order_status"] == "confirmed"
    assert len(state["checkpoints"]) == 1
    assert state["destination"]


def test_eta_anchored_to_delivery_dispatch_time(_memory_state_store):
    """ETA must be the delivery bot's dispatch time + travel, so arrival is
    never before dispatch — for any tier."""
    from datetime import datetime, timedelta

    dispatch = datetime(2026, 6, 25, 12, 0)  # well in the future
    with patch("app.core.delivery_client.get_dispatch_eta", return_value=dispatch):
        state = tracking_service.start_tracking("o_eta", ADDR)

    eta = datetime.fromisoformat(state["eta"])
    # ETA strictly after dispatch (travel time > 0).
    assert eta > dispatch
    # And exactly dispatch + travel time.
    expected = dispatch + timedelta(hours=state["duration_hours"])
    assert abs((eta - expected).total_seconds()) < 1


# ── orchestrator.advance ───────────────────────────────────────────────────

def test_advance_uses_deterministic_fallback_without_llm(_memory_state_store):
    tracking_service.start_tracking("o2", ADDR)
    # No LLM key -> deterministic next stage (dispatched).
    with patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        result = orchestrator.advance("o2")
    assert result["advanced"] is True
    assert result["status"] == "dispatched"


def test_advance_with_llm_choice(_memory_state_store):
    tracking_service.start_tracking("o3", ADDR)
    fake = FakeLLM([text_completion('{"next_status": "dispatched", "note": "left hub"}')])
    with patch("app.core.llm.get_llm_client", return_value=fake), \
         patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        result = orchestrator.advance("o3")
    assert result["advanced"] is True
    assert result["status"] == "dispatched"


def test_advance_reaches_delivered(_memory_state_store):
    tracking_service.start_tracking("o4", ADDR)
    with patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        statuses = []
        for _ in range(6):
            res = orchestrator.advance("o4")
            statuses.append(res["status"])
    assert statuses[-1] == "delivered"
    # Once delivered, further advances are no-ops.
    with patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        again = orchestrator.advance("o4")
    assert again["advanced"] is False


def test_advance_unknown_order(_memory_state_store):
    result = orchestrator.advance("does-not-exist")
    assert result["advanced"] is False


def test_advance_caps_consecutive_holds(_memory_state_store):
    """If the LLM keeps choosing 'hold', the order must still progress: one hold
    is allowed, then the deterministic next stage is forced."""
    tracking_service.start_tracking("o8", ADDR)
    # FakeLLM always says stay at 'pending'.
    holds = FakeLLM([
        text_completion('{"next_status": "pending", "note": "too early"}'),
        text_completion('{"next_status": "pending", "note": "still early"}'),
    ])
    with patch("app.core.llm.get_llm_client", return_value=holds), \
         patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        first = orchestrator.advance("o8")   # allowed hold
        second = orchestrator.advance("o8")  # forced advance
    assert first["advanced"] is False
    assert second["advanced"] is True
    assert second["status"] == "dispatched"


def test_force_advance_ignores_llm_hold(_memory_state_store):
    tracking_service.start_tracking("o8f", ADDR)
    hold = FakeLLM([text_completion('{"next_status": "pending", "note": "too early"}')])
    with patch("app.core.llm.get_llm_client", return_value=hold), \
         patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        res = orchestrator.advance("o8f", force=True)
    assert res["advanced"] is True
    assert res["status"] == "dispatched"


# ── Endpoints ──────────────────────────────────────────────────────────────

def test_start_requires_auth():
    resp = client.post("/tracking/start", json={"order_id": "o9", "destination_address": ADDR})
    assert resp.status_code == 401


def test_start_with_explicit_address(_memory_state_store):
    resp = client.post(
        "/tracking/start",
        json={"order_id": "o5", "destination_address": ADDR, "auto_advance": False},
        headers=auth_header(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == "o5"
    assert body["status"] == "pending"
    assert len(body["checkpoints"]) == 1


def test_get_tracking_state(_memory_state_store):
    client.post(
        "/tracking/start",
        json={"order_id": "o6", "destination_address": ADDR, "auto_advance": False},
        headers=auth_header(),
    )
    resp = client.get("/tracking/o6", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json()["order_id"] == "o6"


def test_get_tracking_404_when_missing(_memory_state_store):
    resp = client.get("/tracking/nope", headers=auth_header())
    assert resp.status_code == 404


def test_advance_endpoint(_memory_state_store):
    client.post(
        "/tracking/start",
        json={"order_id": "o7", "destination_address": ADDR, "auto_advance": False},
        headers=auth_header(),
    )
    with patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        resp = client.post("/tracking/o7/advance", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json()["status"] == "dispatched"


def test_fast_forward_reaches_delivered(_memory_state_store):
    client.post(
        "/tracking/start",
        json={"order_id": "off1", "destination_address": ADDR, "auto_advance": False},
        headers=auth_header(),
    )
    with patch("app.core.backend_client.update_order_status", return_value=True), \
         patch("app.core.delivery_client.notify_checkpoint", return_value=True):
        resp = client.post("/tracking/off1/fast-forward", headers=auth_header())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "delivered"
    # All five stages present in the checkpoint history.
    statuses = [c["status"] for c in body["checkpoints"]]
    assert statuses == ["pending", "dispatched", "in_transit", "out_for_delivery", "delivered"]
