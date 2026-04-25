"""FastAPI dependencies (DB session, Redis, LLM)."""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.ml.interface import LLMInterface


async def get_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncIterator[AsyncSession]:
    yield session


def get_llm(request: Request) -> LLMInterface:
    return request.app.state.llm


def get_redis(request: Request) -> AsyncRedis:
    return request.app.state.redis


def get_intent_classifier(request: Request):
    return request.app.state.intent_classifier
