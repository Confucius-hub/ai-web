"""Smoke tests — проверяют, что Pydantic-схемы и валидаторы работают."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.schemas import (
    ChatRequest,
    ClassifyRequest,
    SessionCreate,
    UserCreate,
)


def test_user_create_ok():
    u = UserCreate(name="caesar", email="c@example.com")
    assert u.name == "caesar"
    assert u.email == "c@example.com"


def test_user_create_no_email_ok():
    u = UserCreate(name="caesar")
    assert u.email is None


def test_user_create_short_name_fails():
    with pytest.raises(ValidationError):
        UserCreate(name="x")  # min_length=2


def test_user_create_bad_email_fails():
    with pytest.raises(ValidationError):
        UserCreate(name="ok", email="not-an-email")


def test_chat_request_creativity_bounds():
    # ge=0.0, le=1.0
    ChatRequest(session_id=1, prompt="hi", creativity=0.0)
    ChatRequest(session_id=1, prompt="hi", creativity=1.0)
    with pytest.raises(ValidationError):
        ChatRequest(session_id=1, prompt="hi", creativity=1.5)
    with pytest.raises(ValidationError):
        ChatRequest(session_id=1, prompt="hi", creativity=-0.1)


def test_chat_request_session_id_positive():
    with pytest.raises(ValidationError):
        ChatRequest(session_id=0, prompt="hi")


def test_chat_request_empty_prompt_fails():
    with pytest.raises(ValidationError):
        ChatRequest(session_id=1, prompt="")


def test_session_create_default_title():
    s = SessionCreate()
    assert s.title == "New chat"


def test_classify_request_min_length():
    ClassifyRequest(text="hi")
    with pytest.raises(ValidationError):
        ClassifyRequest(text="")
