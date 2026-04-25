"""
# Асинхронная очередь задач
Celery-задача: генерация ответа LLM и запись в БД.

Воркер работает в отдельном процессе/контейнере. Статус отслеживается через
таблицу `tasks` в PostgreSQL (Stateless — состояние в БД, не в памяти API).
Воркер также пушит статусы в Redis Pub/Sub для WebSocket-стрима.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import ChatHistory, Task, TaskStatus
from app.ml.factory import build_llm
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)
_settings = get_settings()


# Внутри воркера создаём собственный engine/session (процесс отдельный).
_worker_engine = create_async_engine(_settings.database_url, pool_pre_ping=True)
_worker_session = async_sessionmaker(_worker_engine, expire_on_commit=False)

# Redis для pub/sub — синхронный клиент (Celery task синхронная)
_redis_pub = Redis.from_url(_settings.redis_url, decode_responses=True)


def _publish_status(task_id: str, status: str, extra: dict | None = None) -> None:
    """Публикует событие в Redis — его слушает WebSocket."""
    channel = f"task:{task_id}"
    msg = {"task_id": task_id, "status": status, **(extra or {})}
    try:
        _redis_pub.publish(channel, __import__("json").dumps(msg))
    except Exception as e:
        log.warning("redis_publish_failed", extra={"error": str(e)})


async def _run_task_async(task_id: str, session_id: int, prompt: str,
                          creativity: float, max_new_tokens: int) -> None:
    llm = build_llm(_settings)

    # Помечаем как RUNNING
    async with _worker_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            log.error("task_missing", extra={"task_id": task_id})
            return
        task.status = TaskStatus.RUNNING
        await s.commit()
    _publish_status(task_id, "running")

    try:
        result = await llm.generate(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=creativity,
        )
    except Exception as e:
        log.exception("llm_generate_failed")
        async with _worker_session() as s:
            task = await s.get(Task, task_id)
            task.status = TaskStatus.FAILED
            task.error = str(e)[:500]
            task.finished_at = datetime.now(timezone.utc)
            await s.commit()
        _publish_status(task_id, "failed", {"error": str(e)[:200]})
        return

    # Успех: сохраняем в history + в task
    async with _worker_session() as s:
        msg = ChatHistory(
            session_id=session_id,
            role="assistant",
            content=result.content,
            response_metadata={
                "model": result.model,
                "duration_ms": result.duration_ms,
                **result.metadata,
            },
        )
        s.add(msg)
        task = await s.get(Task, task_id)
        task.status = TaskStatus.SUCCESS
        task.result = result.content
        task.finished_at = datetime.now(timezone.utc)
        await s.commit()
        await s.refresh(msg)
        message_id = msg.id

    _publish_status(
        task_id,
        "success",
        {"result": result.content, "message_id": message_id, "model": result.model},
    )


@celery_app.task(name="chat.generate", bind=True)
def generate_reply_task(
    self, task_id: str, session_id: int, prompt: str,
    creativity: float = 0.7, max_new_tokens: int = 256,
) -> dict:
    """Точка входа воркера."""
    log.info("celery_task_start", extra={"task_id": task_id})
    try:
        asyncio.run(
            _run_task_async(task_id, session_id, prompt, creativity, max_new_tokens)
        )
    except Exception as e:
        log.exception("celery_task_crash")
        _publish_status(task_id, "failed", {"error": str(e)[:200]})
        raise
    return {"task_id": task_id, "done": True}
