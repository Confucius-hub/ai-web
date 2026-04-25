"""
# ORM
Асинхронный движок и фабрика сессий SQLAlchemy 2.0.
Используется asyncpg (не блокирует Event Loop — урок 3).
"""
from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Depends(get_session) — сессия с авто-закрытием.
    SQLAlchemy сам делает rollback при выходе по исключению из `async with`.
    """
    async with async_session_factory() as session:
        yield session


async def dispose_engine() -> None:
    """Graceful shutdown — закрыть пул соединений."""
    await engine.dispose()
