"""Конфигурация Celery"""
from celery import Celery
from ..core.config import settings

celery_app = Celery(
    "kg_mvp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["backend.app.tasks.document_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 час максимум
    worker_prefetch_multiplier=1,  # По одной задаче за раз
)

celery_app.autodiscover_tasks(['backend.app.tasks'])

if __name__ == '__main__':
    celery_app.start()