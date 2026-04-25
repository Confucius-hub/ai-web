"""Users endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.errors import NotFoundError, ValidationAppError
from app.core.logging import log_duration, get_logger
from app.db.models import User
from app.schemas.schemas import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])
log = get_logger(__name__)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    # Валидация данных (Pydantic уже проверил формат)
    existing = await db.scalar(select(User).where(User.name == payload.name))
    if existing:
        raise ValidationAppError(f"User '{payload.name}' already exists")

    user = User(name=payload.name, email=payload.email)
    with log_duration(log, "db.insert_user", name=payload.name):
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.get("", response_model=list[UserRead], summary="List users")
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.scalars(select(User).order_by(User.id.desc()).limit(200))
    return list(result.all())


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user
