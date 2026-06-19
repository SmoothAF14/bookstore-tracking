"""
core/delivery_client.py — httpx client for the delivery service.

Pushes tracking checkpoints to bookstore-delivery so its delivery-status
timeline stays in sync. Best-effort: tracking remains the source of truth via
GET /tracking/{order_id}, so a failed push is logged, not fatal.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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
