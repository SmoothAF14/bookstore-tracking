"""
celery_app.py — Celery application for async tracking tasks.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "bookstore_tracking",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
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
