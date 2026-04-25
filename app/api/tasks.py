"""
Task status endpoints:
  GET  /tasks/{task_id}          — polling
  WS   /ws/tasks/{task_id}       — realtime status через Redis Pub/Sub
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db.models import Task
from app.schemas.schemas import TaskRead

router = APIRouter(tags=["tasks"])
log = get_logger(__name__)


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)) -> Task:
    """# Асинхронная очередь задач — Polling проверка статуса задачи."""
    task = await db.get(Task, task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id} not found")
    return task


@router.websocket("/ws/tasks/{task_id}")
async def ws_task_status(
    websocket: WebSocket,
    task_id: str,
    redis: AsyncRedis = Depends(get_redis),
) -> None:
    """
    # реализована проверка статуса задачи посредством WebSocket
    Клиент подключается → слушает канал Redis `task:{task_id}` → получает
    события (pending/running/success/failed) в реальном времени.
    """
    await websocket.accept()
    pubsub = redis.pubsub()
    channel = f"task:{task_id}"
    await pubsub.subscribe(channel)
    log.info("ws_subscribed", extra={"task_id": task_id})

    try:
        # Сначала отправим текущее состояние (если задача уже завершилась)
        from app.db.session import async_session_factory

        async with async_session_factory() as s:
            task = await s.get(Task, task_id)
            if task is None:
                await websocket.send_json({"error": "task not found"})
                await websocket.close()
                return
            await websocket.send_json(
                {
                    "task_id": task_id,
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                }
            )
            if task.status.value in ("success", "failed"):
                await websocket.close()
                return

        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                # ping для поддержания соединения
                await websocket.send_json({"ping": True})
                continue

            if message and message.get("type") == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    payload = {"raw": data}
                await websocket.send_json(payload)
                if payload.get("status") in ("success", "failed"):
                    break

    except WebSocketDisconnect:
        log.info("ws_client_disconnected", extra={"task_id": task_id})
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass
