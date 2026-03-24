import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(), primary_key=True, default=uuid.uuid4, comment="Primary key."
    )

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="User`s name."
    )

    email: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="User`s email."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), comment="Account creation date."
    )


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="Primary key."
    )

    user_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Request to the API."
    )

    assistant_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, comment="LLM model response."
    )

    temperature: Mapped[float] = mapped_column(
        Float, nullable=False, comment="LLM model creativity param."
    )


class APIKey(Base):
    __tablename__ = "api_key"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="Primary key."
    )

    name: Mapped[str] = mapped_column(Text, nullable=False, comment="Key name.")

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("user.id", ondelete="CASCADE")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), comment="Account creation date."
    )
