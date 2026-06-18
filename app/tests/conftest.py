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
