"""
tasks/tracking_tasks.py — Celery tasks for asynchronous tracking.

advance_tracking runs the orchestrator one step. When auto-advance is on, each
run schedules the next step after a delay, simulating the shipment moving over
time until it's delivered.
"""
import logging

from app.celery_app import celery_app
from app.core import state_store
from app.services import orchestrator

logger = logging.getLogger(__name__)

# Seconds between automatic advance steps (simulated shipment pace).
ADVANCE_INTERVAL_SECONDS = 60


@celery_app.task(name="tracking.advance_tracking")
def advance_tracking(order_id: str, access_token: str | None = None, auto: bool = True):
    """Advance tracking one stage; reschedule until delivered when auto=True."""
    result = orchestrator.advance(order_id, access_token)

    if auto and result.get("status") != "delivered":
        # Schedule the next step unless we've reached the terminal stage.
        advance_tracking.apply_async(
            args=[order_id, access_token, True],
            countdown=ADVANCE_INTERVAL_SECONDS,
        )
    return result


@celery_app.task(name="tracking.recompute_eta")
def recompute_eta(order_id: str):
    """Refresh the mock ETA for an in-flight order (no-op if delivered)."""
    from datetime import datetime, timedelta
    from app.services import tracking_service

    state = state_store.load_state(order_id)
    if not state or state.get("status") == "delivered":
        return {"order_id": order_id, "updated": False}

    route = tracking_service.get_route_for_state(state)
    eta = datetime.utcnow() + timedelta(hours=route.duration_hours)
    state["eta"] = eta.isoformat()
    state_store.save_state(order_id, state)
    return {"order_id": order_id, "updated": True, "eta": state["eta"]}
