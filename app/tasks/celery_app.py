"""
# Асинхронная очередь задач
Celery — брокер Redis, backend Redis. Тяжёлые LLM-запросы выносятся в воркер,
чтобы API не блокировался (паттерн Task Queue из лекции 1).
"""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "ai_web",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["app.tasks.chat_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Graceful Shutdown: даём воркеру 30с на завершение текущей таски
    worker_shutdown_timeout=30,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Разумные лимиты
    task_time_limit=300,  # hard 5 min
    task_soft_time_limit=240,  # soft 4 min
)
