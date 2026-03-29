"""add chat sessions

Revision ID: 9c0a54914c1f
Revises: 5f45e1b6d7a1
Create Date: 2026-03-29 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c0a54914c1f"
down_revision: Union[str, Sequence[str], None] = "5f45e1b6d7a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="Primary key.",
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Chat session creation date.",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_session_user_id"), "chat_session", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_chat_session_created_at"),
        "chat_session",
        ["created_at"],
        unique=False,
    )

    op.add_column("chat_history", sa.Column("session_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_chat_history_session_id"),
        "chat_history",
        ["session_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_chat_history_session_id_chat_session",
        "chat_history",
        "chat_session",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    chat_session_table = sa.table(
        "chat_session",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.UUID()),
        sa.column("created_at", sa.DateTime()),
    )
    chat_history_table = sa.table(
        "chat_history",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.UUID()),
        sa.column("created_at", sa.DateTime()),
        sa.column("session_id", sa.Integer()),
    )

    legacy_history_rows = bind.execute(
        sa.select(
            chat_history_table.c.id,
            chat_history_table.c.user_id,
            chat_history_table.c.created_at,
        )
        .where(chat_history_table.c.user_id.is_not(None))
        .order_by(chat_history_table.c.id)
    ).all()

    for chat_history_row in legacy_history_rows:
        session_id = bind.execute(
            sa.insert(chat_session_table)
            .values(
                user_id=chat_history_row.user_id,
                created_at=chat_history_row.created_at,
            )
            .returning(chat_session_table.c.id)
        ).scalar_one()

        bind.execute(
            sa.update(chat_history_table)
            .where(chat_history_table.c.id == chat_history_row.id)
            .values(session_id=session_id)
        )

    missing_session_links = bind.execute(
        sa.select(sa.func.count())
        .select_from(chat_history_table)
        .where(chat_history_table.c.session_id.is_(None))
    ).scalar_one()
    if missing_session_links == 0:
        op.alter_column("chat_history", "session_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        "fk_chat_history_session_id_chat_session",
        "chat_history",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_chat_history_session_id"), table_name="chat_history")
    op.drop_column("chat_history", "session_id")
    op.drop_index(op.f("ix_chat_session_created_at"), table_name="chat_session")
    op.drop_index(op.f("ix_chat_session_user_id"), table_name="chat_session")
    op.drop_table("chat_session")
