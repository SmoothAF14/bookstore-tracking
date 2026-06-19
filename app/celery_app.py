"""
celery_app.py — Celery application for async tracking tasks.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "bookstore_tracking",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Discover tasks in app.tasks.*
celery_app.autodiscover_tasks(["app.tasks"])
