"""
celery_app.py — Celery application for async tracking tasks.

Minimal bootable Celery app: exposes `celery` so `celery -A app.celery_app`
starts cleanly. Broker/result backend come from env (shared Redis via
REDIS_URL). Tasks and the beat schedule are still placeholders.
"""
import os

from celery import Celery

# Broker defaults to the shared Redis (REDIS_URL); results stay OFF to save
# memory on the free tier.
_broker = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://red-d8ha1s77f7vs73cag08g:6379")
_backend = os.getenv("CELERY_RESULT_BACKEND") or None

celery = Celery("bookstore_tracking", broker=_broker, backend=_backend)

celery.conf.update(
    task_ignore_result=_backend is None,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # Free-tier memory guards.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
)

# TODO: celery.autodiscover_tasks(["app.tasks"]) once tasks are implemented.
# TODO: Define celery.conf.beat_schedule for periodic tracking-advance jobs.
