"""
# Валидация данных
Строгие Pydantic-схемы с типами, ограничениями (ge/le/min_length),
примерами и описаниями для Swagger.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============================================================
# User
# ============================================================
class UserCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"name": "caesar", "email": "caesar@example.com"}})

    name: str = Field(..., min_length=2, max_length=120, description="Unique user name")
    email: EmailStr | None = Field(default=None, description="Optional e-mail")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None = None
    created_at: datetime


# ============================================================
# Chat session
# ============================================================
class SessionCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"title": "Brainstorm about thesis"}})

    title: str = Field(default="New chat", min_length=1, max_length=200)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    created_at: datetime


# ============================================================
# Chat
# ============================================================
class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": 1,
                "prompt": "Give me 3 ideas for a master thesis on Arctic waste detection.",
                "creativity": 0.7,
                "max_new_tokens": 256,
            }
        }
    )

    session_id: int = Field(..., gt=0, description="Existing ChatSession.id")
    prompt: str = Field(..., min_length=1, max_length=4000, description="User prompt")
    # пример из требований: creativity от 0.0 до 1.0
    creativity: float = Field(default=0.7, ge=0.0, le=1.0, description="Temperature")
    max_new_tokens: int = Field(default=256, ge=16, le=2048)


class ChatResponse(BaseModel):
    session_id: int
    message_id: int
    role: Literal["assistant"] = "assistant"
    content: str
    model: str
    duration_ms: float


class ChatMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime


# ============================================================
# Async task
# ============================================================
class TaskSubmitResponse(BaseModel):
    task_id: str = Field(..., description="Celery task id (use for polling)")
    status: Literal["pending"] = "pending"


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: int | None
    status: Literal["pending", "running", "success", "failed"]
    prompt: str
    result: str | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


# ============================================================
# Intent classification (own ONNX model)
# ============================================================
class ClassifyRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"text": "How do I reset my password?"}}
    )

    text: str = Field(..., min_length=1, max_length=2000)


class ClassifyResponse(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    all_scores: dict[str, float]


# ============================================================
# Health
# ============================================================
class HealthComponent(BaseModel):
    status: Literal["ok", "degraded", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    version: str
    components: dict[str, HealthComponent]
