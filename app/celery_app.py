"""
celery_app.py — Celery application for async tracking tasks.

Broker/result backend come from env (shared Redis via REDIS_URL /
CELERY_BROKER_URL) with free-tier memory guards. Tasks in app.tasks are
auto-discovered. The instance is exposed as both `celery` and `celery_app`
so `celery -A app.celery_app` works regardless of which name is referenced.
"""
import os

from celery import Celery

# Broker defaults to the shared Redis (REDIS_URL); results stay OFF by default
# to save memory on the free tier unless a result backend is explicitly set.
_broker = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://localhost:6379")
_backend = os.getenv("CELERY_RESULT_BACKEND") or None

celery = Celery("bookstore_tracking", broker=_broker, backend=_backend)

celery.conf.update(
    task_ignore_result=_backend is None,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # Free-tier memory guards.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
)

# Discover tasks in app.tasks.* (advance_tracking, recompute_eta).
celery.autodiscover_tasks(["app.tasks"])

# Backwards-compatible alias — some modules import `celery_app`.
celery_app = celery
