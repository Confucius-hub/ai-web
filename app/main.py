"""
FastAPI entry point.
Собирает всё вместе: lifespan, error handlers, middleware, routers, метрики.
"""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.api import chat, classify, health, sessions, tasks, users
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.lifespan import lifespan
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger(__name__)

app = FastAPI(
    title="AI Web — Chat Service",
    description="FastAPI + Celery + PostgreSQL + Streamlit + Nginx + Prometheus",
    version=__version__,
    lifespan=lifespan,  # Управление жизненным циклом контекстных переменных
)

# CORS (для прямого доступа к API с UI в dev-режиме)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# # Логирование времени всех этапов работы приложения — per-request timing
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{ms:.2f}"
    log.info(
        "http_request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(ms, 2),
        },
    )
    return response


# # Обработка ошибок
register_error_handlers(app)

# Routers (все под префиксом /api — см. nginx маршрутизацию)
API_PREFIX = "/api"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(sessions.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(classify.router, prefix=API_PREFIX)


# # Метрики — Prometheus instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "ai-web", "version": __version__, "docs": "/docs"}
