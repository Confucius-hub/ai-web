"""Chat sessions endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.db.models import ChatHistory, ChatSession, User
from app.schemas.schemas import ChatMessage, SessionCreate, SessionRead

router = APIRouter(prefix="/users/{user_id}/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    user_id: int,
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
) -> ChatSession:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")

    session = ChatSession(user_id=user_id, title=payload.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[ChatSession]:
    result = await db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.id.desc())
        .limit(100)
    )
    return list(result.all())


@router.get("/{session_id}", response_model=SessionRead)
async def get_session_(
    user_id: int, session_id: int, db: AsyncSession = Depends(get_db)
) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        raise NotFoundError(f"Session {session_id} not found")
    return session


@router.get("/{session_id}/messages", response_model=list[ChatMessage])
async def get_messages(
    user_id: int, session_id: int, db: AsyncSession = Depends(get_db)
) -> list[ChatHistory]:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        raise NotFoundError(f"Session {session_id} not found")
    result = await db.scalars(
        select(ChatHistory)
        .where(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.id)
    )
    return list(result.all())
