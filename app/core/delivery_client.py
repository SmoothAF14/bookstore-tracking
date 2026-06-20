"""
core/delivery_client.py — httpx client for the delivery service.

Two directions of sync with bookstore-delivery:
  * notify_checkpoint — push a new tracking checkpoint so the delivery timeline
    stays current (best-effort).
  * get_dispatch_eta — pull the delivery bot's tier-based dispatch decision so
    the tracking ETA is anchored to the SAME dispatch time the delivery bot
    shows (an order must never arrive before it's dispatched). This is the
    single source of truth for dispatch timing, so the two bots can't drift.

Both are best-effort: tracking remains usable (with a sane fallback) if the
delivery service is unreachable.
"""
import logging
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_dispatch_eta(order_id: str, access_token: str | None = None) -> datetime | None:
    """Pull the delivery bot's projected dispatch time for an order.

    Calls GET {DELIVERY_SERVICE_URL}/delivery/{order_id}/classify and returns
    the parsed `dispatch_eta` (UTC). Returns None on any failure so the caller
    can fall back to a flat lead time.
    """
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    url = f"{settings.DELIVERY_SERVICE_URL}/delivery/{order_id}/classify"
    try:
        with httpx.Client(timeout=5.0, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            raw = (data.get("data") or data).get("dispatch_eta")
            if not raw:
                return None
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.info("Dispatch ETA pull skipped for %s: %s", order_id, exc)
        return None


def notify_checkpoint(order_id: str, checkpoint: dict, access_token: str | None = None) -> bool:
    """Best-effort push of a new checkpoint to the delivery service.

    Targets POST {DELIVERY_SERVICE_URL}/delivery/{order_id}/checkpoint. If the
    delivery service isn't reachable or the endpoint isn't built yet, we log and
    return False — tracking stays authoritative either way.
    """
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    url = f"{settings.DELIVERY_SERVICE_URL}/delivery/{order_id}/checkpoint"
    try:
        with httpx.Client(timeout=5.0, headers=headers) as client:
            resp = client.post(url, json=checkpoint)
            resp.raise_for_status()
            return True
    except httpx.HTTPError as exc:
        logger.info("Delivery checkpoint sync skipped for %s: %s", order_id, exc)
        return False
