"""
core/backend_client.py — httpx client for the Django backend.

Reads an order + its delivery address and writes order-status transitions as
the shipment advances. All calls forward the caller's JWT (the tracking service
shares the backend's SECRET_KEY, so the token is valid against Django).

The Django backend wraps responses in the envelope:
    {"status": {...}, "data": <payload>}
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _client(access_token: str | None = None) -> httpx.Client:
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return httpx.Client(base_url=settings.DJANGO_API_URL, timeout=10.0, headers=headers)


def _unwrap(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def get_order(order_id: str, access_token: str | None = None) -> dict:
    """Fetch an order (includes its `delivery` block with the address)."""
    with _client(access_token) as client:
        resp = client.get(f"/api/orders/{order_id}/")
        resp.raise_for_status()
        return _unwrap(resp.json()) or {}


def get_delivery_address(order: dict) -> str | None:
    """Build a single-line destination address from an order's delivery block."""
    d = (order or {}).get("delivery") or {}
    if not d:
        return None
    parts = [
        d.get("line1"), d.get("line2"), d.get("city"),
        d.get("state"), d.get("postal_code"), d.get("country"),
    ]
    line = ", ".join(p for p in parts if p)
    return line or None


def update_order_status(order_id: str, order_status: str, access_token: str | None = None) -> bool:
    """Patch an order's status on the backend. Returns True on success.

    Best-effort: logs and returns False on failure so a tracking advance never
    hard-crashes on a transient backend hiccup.
    """
    try:
        with _client(access_token) as client:
            resp = client.patch(
                f"/api/orders/{order_id}/", json={"status": order_status}
            )
            resp.raise_for_status()
            return True
    except httpx.HTTPError as exc:
        logger.warning("Failed to update order %s status=%s: %s", order_id, order_status, exc)
        return False
