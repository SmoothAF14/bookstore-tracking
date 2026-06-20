"""
services/tracking_service.py — Tracking checkpoint generation + state.

Builds the initial tracking state (route, ETA, first checkpoint) from mock map
data, and produces the ordered checkpoint sequence the shipment moves through.
The orchestrator drives advancing between stages.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.core import maps_client, state_store
from app.core.config import settings
from app.schemas.tracking import STATUS_TO_ORDER_STATUS

logger = logging.getLogger(__name__)

# The ordered stages a shipment advances through.
STAGE_ORDER = ["pending", "dispatched", "in_transit", "out_for_delivery", "delivered"]

# How far along the origin→destination line the shipment is at each stage.
# Used to compute a live map position from the mock route.
STAGE_PROGRESS = {
    "pending": 0.0,
    "dispatched": 0.08,
    "in_transit": 0.5,
    "out_for_delivery": 0.85,
    "delivered": 1.0,
}

# Human-readable labels per stage.
STAGE_LABELS = {
    "pending": "Order confirmed",
    "dispatched": "Dispatched from fulfilment centre",
    "in_transit": "In transit",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
}


def next_stage(status: str) -> str | None:
    """Return the stage after `status`, or None if already delivered."""
    try:
        idx = STAGE_ORDER.index(status)
    except ValueError:
        return None
    return STAGE_ORDER[idx + 1] if idx + 1 < len(STAGE_ORDER) else None


def build_checkpoint(status: str, route, when: datetime | None = None) -> dict:
    """Construct a checkpoint dict for a given stage using the mock route."""
    when = when or datetime.utcnow()
    location = None
    point = None

    if status == "dispatched":
        location = route.origin.get("label")
        point = {"lat": route.origin["lat"], "lng": route.origin["lng"], "label": location}
    elif status == "in_transit":
        hub = route.hubs[len(route.hubs) // 2] if route.hubs else "Regional Hub"
        location = hub
    elif status == "out_for_delivery":
        location = "Local Delivery Centre"
    elif status == "delivered":
        location = route.destination.get("label")
        point = {
            "lat": route.destination["lat"],
            "lng": route.destination["lng"],
            "label": location,
        }

    return {
        "status": status,
        "label": STAGE_LABELS.get(status, status.replace("_", " ").title()),
        "description": None,
        "location": location,
        "point": point,
        "timestamp": when.isoformat(),
        "is_current": True,
    }


def start_tracking(order_id: str, destination_address: str, access_token: str | None = None) -> dict:
    """Initialise tracking state for an order and persist it.

    Creates the route + ETA from mock maps and the first ('pending') checkpoint.
    Returns the new state dict.

    The ETA is anchored to the DELIVERY bot's tier-based dispatch time (pulled
    via the delivery client) plus travel time, so arrival can never precede
    dispatch — regardless of the order's tier (express/standard/bulk). If the
    delivery service is unreachable, we fall back to a flat DISPATCH_LEAD_HOURS.
    """
    from app.core import delivery_client

    route = maps_client.get_route(destination_address)
    now = datetime.utcnow()

    # Prefer the delivery bot's actual dispatch time (single source of truth for
    # dispatch timing). Fall back to a flat lead time if it's unavailable.
    dispatch_at = delivery_client.get_dispatch_eta(order_id, access_token)
    if dispatch_at is not None:
        # Normalise to naive UTC to match the rest of this module's datetimes.
        if dispatch_at.tzinfo is not None:
            dispatch_at = dispatch_at.astimezone(timezone.utc).replace(tzinfo=None)
        # Never let a stale/past dispatch time pull the ETA before "now".
        dispatch_at = max(dispatch_at, now)
        eta = dispatch_at + timedelta(hours=route.duration_hours)
    else:
        eta = now + timedelta(hours=settings.DISPATCH_LEAD_HOURS + route.duration_hours)

    first = build_checkpoint("pending", route, now)
    first["label"] = STAGE_LABELS["pending"]

    state = {
        "order_id": order_id,
        "status": "pending",
        "order_status": STATUS_TO_ORDER_STATUS["pending"],
        "origin": route.origin.get("label"),
        "destination": route.destination.get("label"),
        "origin_point": route.origin,
        "destination_point": route.destination,
        "distance_km": route.distance_km,
        "duration_hours": route.duration_hours,
        "eta": eta.isoformat(),
        "dispatch_at": dispatch_at.isoformat() if dispatch_at is not None else None,
        "destination_address": destination_address,
        "checkpoints": [first],
        "updated_at": now.isoformat(),
    }
    state_store.save_state(order_id, state)
    logger.info("Started tracking for order %s → %s", order_id, destination_address)
    return state


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def compute_current_point(state: dict) -> dict | None:
    """Interpolate the shipment's live position along the mock route.

    Linearly blends origin → destination by the current stage's progress so the
    map can show the parcel moving as it advances. Returns None if the route's
    geo points aren't available (e.g. tracking started before they were stored).
    """
    origin = state.get("origin_point")
    dest = state.get("destination_point")
    if not origin or not dest:
        return None
    t = STAGE_PROGRESS.get(state.get("status"), 0.0)
    if t <= 0:
        label = origin.get("label")
    elif t >= 1:
        label = dest.get("label")
    else:
        label = "In transit"
    return {
        "lat": round(_lerp(origin["lat"], dest["lat"], t), 5),
        "lng": round(_lerp(origin["lng"], dest["lng"], t), 5),
        "label": label,
    }


def hydrate(state: dict | None) -> dict | None:
    """Return a copy of the state augmented with the live current_point."""
    if not state:
        return state
    enriched = dict(state)
    enriched["current_point"] = compute_current_point(state)
    return enriched


def get_route_for_state(state: dict):
    """Rebuild the mock route for an existing state (deterministic from address)."""
    return maps_client.get_route(state.get("destination_address") or "")
