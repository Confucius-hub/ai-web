"""
Chat endpoints:
  POST /chat       — синхронный (быстрый ответ, для коротких промптов)
  POST /chat/async — ставит задачу в Celery-очередь, возвращает task_id
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_llm
from app.core.errors import NotFoundError
from app.core.logging import get_logger, log_duration
from app.db.models import ChatHistory, ChatSession, Task, TaskStatus
from app.ml.interface import LLMInterface
from app.schemas.schemas import ChatRequest, ChatResponse, TaskSubmitResponse
from app.tasks.chat_tasks import generate_reply_task

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger(__name__)


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_sync(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMInterface = Depends(get_llm),
) -> ChatResponse:
    """Синхронный чат. Подходит для коротких промптов."""
    session = await db.get(ChatSession, payload.session_id)
    if session is None:
        raise NotFoundError(f"Session {payload.session_id} not found")

    # Сохраняем user-сообщение
    user_msg = ChatHistory(
        session_id=payload.session_id,
        role="user",
        content=payload.prompt,
        response_metadata={},
    )
    db.add(user_msg)
    await db.flush()

    # Логирование времени всех этапов работы приложения
    with log_duration(log, "llm.generate", session_id=payload.session_id):
        result = await llm.generate(
            payload.prompt,
            max_new_tokens=payload.max_new_tokens,
            temperature=payload.creativity,
        )

    asst_msg = ChatHistory(
        session_id=payload.session_id,
        role="assistant",
        content=result.content,
        response_metadata={
            "model": result.model,
            "duration_ms": result.duration_ms,
            **result.metadata,
        },
    )
    db.add(asst_msg)
    await db.commit()
    await db.refresh(asst_msg)

    return ChatResponse(
        session_id=payload.session_id,
        message_id=asst_msg.id,
        content=result.content,
        model=result.model,
        duration_ms=result.duration_ms,
    )


@router.post(
    "/async",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a chat request to the background queue (Celery)",
)
async def chat_async(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskSubmitResponse:
    """
    # Асинхронная очередь задач
    Возвращает 202 Accepted с task_id. Фактический ответ придёт позже —
    проверяй через GET /tasks/{task_id} или WebSocket /ws/tasks/{task_id}.
    """
    session = await db.get(ChatSession, payload.session_id)
    if session is None:
        raise NotFoundError(f"Session {payload.session_id} not found")

    task_id = uuid.uuid4().hex
    task = Task(
        id=task_id,
        session_id=payload.session_id,
        status=TaskStatus.PENDING,
        prompt=payload.prompt,
    )
    db.add(task)
    # Также сохраняем user-сообщение в историю
    user_msg = ChatHistory(
        session_id=payload.session_id,
        role="user",
        content=payload.prompt,
        response_metadata={"async_task_id": task_id},
    )
    db.add(user_msg)
    await db.commit()

    generate_reply_task.apply_async(
        kwargs={
            "task_id": task_id,
            "session_id": payload.session_id,
            "prompt": payload.prompt,
            "creativity": payload.creativity,
            "max_new_tokens": payload.max_new_tokens,
        },
        task_id=task_id,
    )
    return TaskSubmitResponse(task_id=task_id)
