"""
test_health.py — Health endpoint tests.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_returns_ok_status():
    resp = client.get("/health")
    assert resp.json() == {"status": "ok"}
