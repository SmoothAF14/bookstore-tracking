"""
core/state_store.py — Redis-backed tracking state store.

Tracking state (current status, route, ETA, checkpoint history) is persisted in
Redis so the API, Celery worker, and beat scheduler all share one source of
truth. Keys: tracking:<order_id>.
"""
import json
import logging
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_TTL_SECONDS = 7 * 24 * 3600  # keep tracking state for a week
_client: Optional[redis.Redis] = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.CELERY_RESULT_BACKEND, decode_responses=True
        )
    return _client


def _key(order_id: str) -> str:
    return f"tracking:{order_id}"


def load_state(order_id: str) -> Optional[dict]:
    """Return the stored tracking state dict for an order, or None."""
    try:
        raw = _redis().get(_key(order_id))
    except redis.RedisError as exc:
        logger.error("Redis read failed for %s: %s", order_id, exc)
        return None
    return json.loads(raw) if raw else None


def save_state(order_id: str, state: dict) -> None:
    """Persist the tracking state dict for an order."""
    try:
        _redis().setex(_key(order_id), _TTL_SECONDS, json.dumps(state, default=str))
    except redis.RedisError as exc:
        logger.error("Redis write failed for %s: %s", order_id, exc)
