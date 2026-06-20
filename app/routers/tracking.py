"""
routers/tracking.py — Tracking endpoints.

  POST /tracking/start        — begin tracking an order (enqueues advance jobs)
  GET  /tracking/{order_id}   — current tracking state + checkpoints
  POST /tracking/{order_id}/advance — advance one step now (manual/testing)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core import backend_client, state_store
from app.core.auth import AuthenticatedUser, require_user
from app.schemas.tracking import (
    AdvanceResponse,
    StartTrackingRequest,
    TrackingStateResponse,
)
from app.services import orchestrator, tracking_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=TrackingStateResponse, summary="Start tracking an order")
def start_tracking(
    request: StartTrackingRequest,
    user: AuthenticatedUser = Depends(require_user),
):
    """Begin tracking. Reads the delivery address from the order unless one is
    supplied, creates the initial state, and (optionally) schedules auto-advance
    Celery jobs."""
    destination = request.destination_address

    if not destination:
        try:
            order = backend_client.get_order(request.order_id, user.access_token)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"Could not read order: {exc}") from exc
        destination = backend_client.get_delivery_address(order)

    if not destination:
        raise HTTPException(
            status_code=400,
            detail="No delivery address found for this order. Provide destination_address.",
        )

    state = tracking_service.start_tracking(request.order_id, destination)

    if request.auto_advance:
        try:
            from app.tasks.tracking_tasks import advance_tracking
            advance_tracking.apply_async(
                args=[request.order_id, user.access_token, True], countdown=10
            )
        except Exception as exc:  # noqa: BLE001 — broker down shouldn't fail the request
            logger.warning("Could not enqueue auto-advance for %s: %s", request.order_id, exc)

    return tracking_service.hydrate(state)


@router.get("/{order_id}", response_model=TrackingStateResponse, summary="Get tracking state")
def get_tracking(order_id: str, user: AuthenticatedUser = Depends(require_user)):
    state = state_store.load_state(order_id)
    if not state:
        raise HTTPException(status_code=404, detail="No tracking found for this order.")
    return tracking_service.hydrate(state)


@router.post("/{order_id}/advance", response_model=AdvanceResponse, summary="Advance one step")
def advance_now(order_id: str, user: AuthenticatedUser = Depends(require_user)):
    """Advance tracking one stage immediately (manual trigger / testing)."""
    return orchestrator.advance(order_id, user.access_token)


@router.post(
    "/{order_id}/fast-forward",
    response_model=TrackingStateResponse,
    summary="Advance through ALL remaining stages now (testing)",
)
def fast_forward(order_id: str, user: AuthenticatedUser = Depends(require_user)):
    """Synchronously advance the shipment through every remaining stage until
    delivered, in one request.

    This exists so the full workflow can be tested end-to-end WITHOUT waiting
    for the timed Celery auto-advance (which also can't fire while a free-tier
    container is asleep). Each step still writes the order-status transition to
    the backend and notifies the delivery service, exactly like the timed path.
    """
    state = state_store.load_state(order_id)
    if not state:
        raise HTTPException(status_code=404, detail="No tracking found for this order.")

    # Bounded loop (max = number of stages) so a bug can never spin forever.
    for _ in range(len(tracking_service.STAGE_ORDER)):
        result = orchestrator.advance(order_id, user.access_token, force=True)
        if not result.get("advanced"):
            break
        if result.get("status") == "delivered":
            break

    return tracking_service.hydrate(state_store.load_state(order_id))
