"""
tests/conftest.py — shared fixtures.

Configures the JWT secret and replaces the Redis-backed state store with an
in-memory dict so tests need no Redis.
"""
import pytest

from app.core import state_store
from app.core.config import settings
from app.tests.helpers import TEST_JWT_SECRET


@pytest.fixture(autouse=True)
def _configure_auth():
    original_secret = settings.JWT_SECRET
    original_require = settings.REQUIRE_AUTH
    settings.JWT_SECRET = TEST_JWT_SECRET
    settings.REQUIRE_AUTH = True
    yield
    settings.JWT_SECRET = original_secret
    settings.REQUIRE_AUTH = original_require


@pytest.fixture(autouse=True)
def _memory_state_store(monkeypatch):
    """Swap Redis for an in-memory dict so load/save work without Redis."""
    store: dict[str, dict] = {}
    monkeypatch.setattr(state_store, "load_state", lambda oid: store.get(oid))
    monkeypatch.setattr(state_store, "save_state", lambda oid, s: store.__setitem__(oid, s))
    return store


@pytest.fixture(autouse=True)
def _no_delivery_calls(monkeypatch):
    """Stub the delivery client so start_tracking doesn't make real HTTP calls.

    Tests that want to assert dispatch-ETA behaviour can override get_dispatch_eta
    via their own patch; by default it returns None (flat-lead fallback) and the
    checkpoint push is a no-op.
    """
    from app.core import delivery_client
    monkeypatch.setattr(delivery_client, "get_dispatch_eta", lambda oid, token=None: None)
    monkeypatch.setattr(delivery_client, "notify_checkpoint", lambda oid, cp, token=None: True)
