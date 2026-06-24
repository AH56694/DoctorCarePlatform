"""initial schema

Revision ID: 20260624_0001
Revises:
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260624_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_roles_role", "user_roles", ["role"])

    op.create_table(
        "job_postings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("employer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("city", sa.String(80), nullable=False, server_default=""),
        sa.Column("care_level", sa.String(64), nullable=False, server_default=""),
        sa.Column("budget_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job_postings.id", ondelete="CASCADE")),
        sa.Column("caregiver_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("cover_letter", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id")),
        sa.Column("kind", sa.String(32), nullable=False, server_default="care_chat"),
        sa.Column("title", sa.String(160), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE")),
        sa.Column("sender_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sender_type", sa.String(32), nullable=False, server_default="user"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("assistant_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("intent_category", sa.String(64), nullable=False),
        sa.Column("intent_subcategory", sa.String(64), nullable=False, server_default=""),
        sa.Column("intent_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cache_hit_level", sa.String(16), nullable=False, server_default="miss"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_messages_intent_category", "ai_messages", ["intent_category"])
    op.create_index("ix_ai_messages_intent_subcategory", "ai_messages", ["intent_subcategory"])

    op.create_table(
        "medical_cases",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("patient_owner_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id")),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("encryption_key_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("subcategory", sa.String(64), nullable=False),
        sa.Column("collection", sa.String(128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_knowledge_chunks_category", "ai_knowledge_chunks", ["category"])
    op.create_index("ix_ai_knowledge_chunks_subcategory", "ai_knowledge_chunks", ["subcategory"])
    op.create_index("ix_ai_knowledge_chunks_collection", "ai_knowledge_chunks", ["collection"])

    op.create_table(
        "ai_semantic_cache",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("subcategory", sa.String(64), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("cache_policy", sa.String(32), nullable=False, server_default="context_only"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "sms_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("template_code", sa.String(80), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sms_notifications_phone", "sms_notifications", ["phone"])


def downgrade() -> None:
    for table_name in [
        "sms_notifications",
        "ai_semantic_cache",
        "ai_knowledge_chunks",
        "medical_cases",
        "ai_messages",
        "messages",
        "conversations",
        "applications",
        "job_postings",
        "user_roles",
        "users",
    ]:
        op.drop_table(table_name)
