"""
# ORM
ORM-модели: User -> ChatSession -> ChatHistory (как в базовой версии),
плюс Task для трекинга фоновых задач Celery.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New chat", nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatHistory"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatHistory.id",
    )


class ChatHistory(Base, TimestampMixin):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # response_metadata: имя модели, время генерации и т.п. (JSONB)
    response_metadata: Mapped[dict] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Task(Base, TimestampMixin):
    """
    # Stateless архитектура
    Состояние задач вынесено в БД (а не в памяти процесса).
    Это позволяет масштабировать API горизонтально — любая реплика
    может прочитать статус задачи.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # celery task_id (uuid4)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status_enum"),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
