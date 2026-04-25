"""
# API Health Check
/health проверяет не только «сервер жив», но и доступность БД, Redis
и готовность LLM-модели (Model-in-App).
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.api.deps import get_db, get_llm, get_redis
from app.ml.interface import LLMInterface
from app.schemas.schemas import HealthComponent, HealthResponse

router = APIRouter(tags=["health"])


async def _check_db(db: AsyncSession) -> HealthComponent:
    # Допустимое использование text() — это healthcheck-пинг, а не бизнес-запрос.
    # Бизнес-логика везде в коде идёт через ORM (см. app/api/*.py).
    try:
        await db.execute(text("SELECT 1"))
        return HealthComponent(status="ok")
    except Exception as e:
        return HealthComponent(status="down", detail=str(e)[:200])


async def _check_redis(redis: AsyncRedis) -> HealthComponent:
    try:
        pong = await asyncio.wait_for(redis.ping(), timeout=2.0)
        return HealthComponent(status="ok" if pong else "down")
    except Exception as e:
        return HealthComponent(status="down", detail=str(e)[:200])


async def _check_llm(llm: LLMInterface) -> HealthComponent:
    try:
        ok = await asyncio.wait_for(llm.healthcheck(), timeout=3.0)
        return HealthComponent(status="ok" if ok else "degraded")
    except Exception as e:
        return HealthComponent(status="degraded", detail=str(e)[:200])


@router.get("/health", response_model=HealthResponse)
async def health(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    llm: LLMInterface = Depends(get_llm),
) -> HealthResponse:
    db_c, redis_c, llm_c = await asyncio.gather(
        _check_db(db), _check_redis(redis), _check_llm(llm)
    )
    components = {"database": db_c, "redis": redis_c, "llm": llm_c}

    if any(c.status == "down" for c in components.values()):
        overall = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(c.status == "degraded" for c in components.values()):
        overall = "degraded"
    else:
        overall = "ok"

    return HealthResponse(status=overall, version=__version__, components=components)
