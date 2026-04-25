"""
# Управление жизненным циклом контекстных переменных
Lifespan инициализирует подключения (БД, Redis) и загружает модель в память
один раз при старте сервера (Model-in-App паттерн из лекции).

Это решает проблему «холодного старта» — модель не грузится на каждый запрос.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis as AsyncRedis

from app.core.config import get_settings
from app.db.session import dispose_engine, engine
from app.ml.factory import build_llm
from app.ml.local_onnx import LocalIntentClassifier

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("lifespan_startup", extra={"env": settings.app_env})

    # 1. DB engine уже создан при импорте; проверим соединение (healthcheck-пинг)
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("db_connected")
    except Exception as e:
        log.error("db_connect_failed", extra={"error": str(e)})
        # Не падаем — /health вернёт degraded

    # 2. Redis
    redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        log.info("redis_connected")
    except Exception as e:
        log.error("redis_connect_failed", extra={"error": str(e)})
    app.state.redis = redis

    # 3. LLM клиент (Model-in-App — создаётся ОДИН раз)
    app.state.llm = build_llm(settings)
    log.info("llm_ready", extra={"mode": settings.llm_mode, "model": settings.llm_model})

    # 4. Локальный ONNX классификатор намерений (Своя модель + Оптимизация инференса)
    try:
        app.state.intent_classifier = LocalIntentClassifier(
            model_path=settings.local_model_path,
            labels_path=settings.local_labels_path,
        )
        log.info("intent_classifier_loaded")
    except Exception as e:
        log.warning("intent_classifier_missing", extra={"error": str(e)})
        app.state.intent_classifier = None

    yield

    # --- Shutdown (Graceful Shutdown) ---
    log.info("lifespan_shutdown")
    try:
        await redis.close()
    except Exception:
        pass
    await dispose_engine()
    log.info("lifespan_shutdown_done")
