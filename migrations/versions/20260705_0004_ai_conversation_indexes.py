"""add ai conversation lookup indexes

Revision ID: 20260705_0004
Revises: 20260624_0003
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260705_0004"
down_revision: str | None = "20260624_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_ai_sessions_user_updated_created",
        "ai_sessions",
        ["user_id", "updated_at", "created_at"],
    )
    op.create_index(
        "ix_ai_messages_session_created",
        "ai_messages",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_ai_messages_conversation_created",
        "ai_messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_messages_conversation_created", table_name="ai_messages")
    op.drop_index("ix_ai_messages_session_created", table_name="ai_messages")
    op.drop_index("ix_ai_sessions_user_updated_created", table_name="ai_sessions")
