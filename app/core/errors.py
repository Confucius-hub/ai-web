"""
# Обработка ошибок
Кастомные исключения приложения и обработчики для FastAPI.
Возвращают понятный JSON и корректные HTTP-статусы (400, 404, 422, 500, 503).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

log = logging.getLogger(__name__)


# --- Custom exceptions ---
class AppError(Exception):
    """Базовое бизнес-исключение приложения."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationAppError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "validation_error"


class LLMError(AppError):
    """Ошибка работы с LLM-провайдером (таймаут, 5xx, bad API key)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "llm_unavailable"


class DependencyUnavailable(AppError):
    """БД или Redis недоступны."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "dependency_unavailable"


# --- Handlers ---
def _json_error(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log.warning(
        "app_error",
        extra={"path": request.url.path, "code": exc.code, "message": exc.message},
    )
    return _json_error(exc.status_code, exc.code, exc.message, exc.details or None)


async def validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _json_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "Request validation failed",
        details=exc.errors(),
    )


async def integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    log.warning("db_integrity_error", extra={"path": request.url.path})
    return _json_error(
        status.HTTP_409_CONFLICT,
        "conflict",
        "Resource conflict (e.g. duplicate or broken relation)",
    )


async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    log.exception("db_error", extra={"path": request.url.path})
    return _json_error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "database_unavailable",
        "Database error",
    )


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", extra={"path": request.url.path})
    return _json_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Internal server error",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(IntegrityError, integrity_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_handler)
    app.add_exception_handler(Exception, unhandled_handler)
