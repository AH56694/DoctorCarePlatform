"""complete platform database design

Revision ID: 20260624_0003
Revises: 20260624_0002
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260624_0003"
down_revision: str | None = "20260624_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_postings", sa.Column("patient_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_job_postings_patient_id_users", "job_postings", "users", ["patient_id"], ["id"])
    op.add_column("job_postings", sa.Column("care_type", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("job_postings", sa.Column("location", sa.String(length=160), nullable=False, server_default=""))
    op.add_column(
        "job_postings",
        sa.Column("schedule", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "job_postings",
        sa.Column("salary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column("job_postings", sa.Column("special_requirements", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_job_postings_patient_id", "job_postings", ["patient_id"])
    op.create_index("ix_job_postings_status", "job_postings", ["status"])
    op.create_index("ix_job_postings_city", "job_postings", ["city"])

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("caregiver_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("patient_id", "caregiver_id", "job_id", name="uq_invitations_patient_caregiver_job"),
    )
    op.create_index("ix_invitations_patient_id", "invitations", ["patient_id"])
    op.create_index("ix_invitations_caregiver_id", "invitations", ["caregiver_id"])
    op.create_index("ix_invitations_status", "invitations", ["status"])

    op.add_column("conversations", sa.Column("participant_a", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("conversations", sa.Column("participant_b", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("conversations", sa.Column("source_type", sa.String(length=32), nullable=False, server_default=""))
    op.add_column("conversations", sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_conversations_participant_a_users", "conversations", "users", ["participant_a"], ["id"])
    op.create_foreign_key("fk_conversations_participant_b_users", "conversations", "users", ["participant_b"], ["id"])
    op.create_index("ix_conversations_participant_a", "conversations", ["participant_a"])
    op.create_index("ix_conversations_participant_b", "conversations", ["participant_b"])
    op.create_index("ix_conversations_source", "conversations", ["source_type", "source_id"])

    op.add_column("messages", sa.Column("content", sa.Text(), nullable=False, server_default=""))
    op.add_column("messages", sa.Column("attachment_url", sa.String(length=500), nullable=False, server_default=""))
    op.add_column("messages", sa.Column("attachment_type", sa.String(length=64), nullable=False, server_default=""))
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])

    op.create_table(
        "ai_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role_context", sa.String(length=32), nullable=False, server_default="patient"),
        sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("risk_flag", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_sessions_user_id", "ai_sessions", ["user_id"])
    op.create_index("ix_ai_sessions_risk_flag", "ai_sessions", ["risk_flag"])

    op.add_column("ai_messages", sa.Column("session_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("ai_messages", sa.Column("sender", sa.String(length=16), nullable=False, server_default="user"))
    op.add_column("ai_messages", sa.Column("content", sa.Text(), nullable=False, server_default=""))
    op.create_foreign_key("fk_ai_messages_session_id_ai_sessions", "ai_messages", "ai_sessions", ["session_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_ai_messages_session_id", "ai_messages", ["session_id"])

    op.add_column("medical_cases", sa.Column("patient_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("medical_cases", sa.Column("summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("medical_cases", sa.Column("public_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("medical_cases", sa.Column("history_encrypted", sa.Text(), nullable=False, server_default=""))
    op.add_column("medical_cases", sa.Column("symptoms_encrypted", sa.Text(), nullable=False, server_default=""))
    op.add_column("medical_cases", sa.Column("medications_encrypted", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "medical_cases",
        sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column("medical_cases", sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"))
    op.add_column("medical_cases", sa.Column("linked_ai_session_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column(
        "medical_cases",
        sa.Column("encryption_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.create_foreign_key("fk_medical_cases_patient_id_users", "medical_cases", "users", ["patient_id"], ["id"])
    op.create_foreign_key(
        "fk_medical_cases_linked_ai_session_id_ai_sessions",
        "medical_cases",
        "ai_sessions",
        ["linked_ai_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_medical_cases_patient_id", "medical_cases", ["patient_id"])
    op.create_index("ix_medical_cases_visibility", "medical_cases", ["visibility"])

    op.create_table(
        "ai_model_configs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="deepseek"),
        sa.Column("model_name", sa.String(length=120), nullable=False, server_default="deepseek-chat"),
        sa.Column("base_url", sa.String(length=500), nullable=False, server_default="https://api.deepseek.com"),
        sa.Column("api_key_ref", sa.String(length=120), nullable=False, server_default="LLM_API_KEY"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_model_configs_provider", "ai_model_configs", ["provider"])
    op.create_index("ix_ai_model_configs_is_active", "ai_model_configs", ["is_active"])
    op.execute(
        """
        INSERT INTO ai_model_configs (
            id, provider, model_name, base_url, api_key_ref, temperature, max_tokens, is_active, parameters
        )
        VALUES (
            '00000000-0000-0000-0000-000000000003', 'deepseek', 'deepseek-chat', 'https://api.deepseek.com',
            'LLM_API_KEY', 0.3, 2048, true, '{}'::jsonb
        )
        """
    )

    op.execute("ALTER TABLE ai_knowledge_chunks ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX ix_ai_knowledge_chunks_embedding "
        "ON ai_knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.add_column("ai_semantic_cache", sa.Column("query_embedding", sa.Text(), nullable=True))
    op.execute("ALTER TABLE ai_semantic_cache ALTER COLUMN query_embedding TYPE vector(768) USING query_embedding::vector")
    op.add_column("ai_semantic_cache", sa.Column("cached_answer", sa.Text(), nullable=False, server_default=""))
    op.add_column("ai_semantic_cache", sa.Column("intent_category", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("ai_semantic_cache", sa.Column("reusable_as_final", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ai_semantic_cache", sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_semantic_cache", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_ai_semantic_cache_intent_category", "ai_semantic_cache", ["intent_category"])
    op.execute(
        "CREATE INDEX ix_ai_semantic_cache_query_embedding "
        "ON ai_semantic_cache USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewee_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_reviews_score_range"),
        sa.UniqueConstraint("conversation_id", "reviewer_id", name="uq_reviews_conversation_reviewer"),
    )
    op.create_index("ix_reviews_reviewee_id", "reviews", ["reviewee_id"])

    op.add_column("sms_notifications", sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("sms_notifications", sa.Column("scene", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("sms_notifications", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_sms_notifications_user_id_users", "sms_notifications", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_sms_notifications_user_id", "sms_notifications", ["user_id"])
    op.create_index("ix_sms_notifications_scene", "sms_notifications", ["scene"])

    op.create_table(
        "admin_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("admin_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("target_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("target", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_admin_logs_action", "admin_logs", ["action"])
    op.create_index("ix_admin_logs_admin_id", "admin_logs", ["admin_id"])
    op.create_index("ix_admin_logs_target", "admin_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_logs_target", table_name="admin_logs")
    op.drop_index("ix_admin_logs_admin_id", table_name="admin_logs")
    op.drop_index("ix_admin_logs_action", table_name="admin_logs")
    op.drop_table("admin_logs")

    op.drop_index("ix_sms_notifications_scene", table_name="sms_notifications")
    op.drop_index("ix_sms_notifications_user_id", table_name="sms_notifications")
    op.drop_constraint("fk_sms_notifications_user_id_users", "sms_notifications", type_="foreignkey")
    op.drop_column("sms_notifications", "sent_at")
    op.drop_column("sms_notifications", "scene")
    op.drop_column("sms_notifications", "user_id")

    op.drop_index("ix_reviews_reviewee_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_ai_semantic_cache_query_embedding", table_name="ai_semantic_cache")
    op.drop_index("ix_ai_semantic_cache_intent_category", table_name="ai_semantic_cache")
    op.drop_column("ai_semantic_cache", "expires_at")
    op.drop_column("ai_semantic_cache", "ttl_seconds")
    op.drop_column("ai_semantic_cache", "reusable_as_final")
    op.drop_column("ai_semantic_cache", "intent_category")
    op.drop_column("ai_semantic_cache", "cached_answer")
    op.drop_column("ai_semantic_cache", "query_embedding")

    op.drop_index("ix_ai_knowledge_chunks_embedding", table_name="ai_knowledge_chunks")
    op.drop_column("ai_knowledge_chunks", "embedding")

    op.drop_index("ix_ai_model_configs_is_active", table_name="ai_model_configs")
    op.drop_index("ix_ai_model_configs_provider", table_name="ai_model_configs")
    op.drop_table("ai_model_configs")

    op.drop_index("ix_medical_cases_visibility", table_name="medical_cases")
    op.drop_index("ix_medical_cases_patient_id", table_name="medical_cases")
    op.drop_constraint("fk_medical_cases_linked_ai_session_id_ai_sessions", "medical_cases", type_="foreignkey")
    op.drop_constraint("fk_medical_cases_patient_id_users", "medical_cases", type_="foreignkey")
    op.drop_column("medical_cases", "encryption_metadata")
    op.drop_column("medical_cases", "linked_ai_session_id")
    op.drop_column("medical_cases", "visibility")
    op.drop_column("medical_cases", "attachments")
    op.drop_column("medical_cases", "medications_encrypted")
    op.drop_column("medical_cases", "symptoms_encrypted")
    op.drop_column("medical_cases", "history_encrypted")
    op.drop_column("medical_cases", "public_summary")
    op.drop_column("medical_cases", "summary")
    op.drop_column("medical_cases", "patient_id")

    op.drop_index("ix_ai_messages_session_id", table_name="ai_messages")
    op.drop_constraint("fk_ai_messages_session_id_ai_sessions", "ai_messages", type_="foreignkey")
    op.drop_column("ai_messages", "content")
    op.drop_column("ai_messages", "sender")
    op.drop_column("ai_messages", "session_id")
    op.drop_index("ix_ai_sessions_risk_flag", table_name="ai_sessions")
    op.drop_index("ix_ai_sessions_user_id", table_name="ai_sessions")
    op.drop_table("ai_sessions")

    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_column("messages", "attachment_type")
    op.drop_column("messages", "attachment_url")
    op.drop_column("messages", "content")

    op.drop_index("ix_conversations_source", table_name="conversations")
    op.drop_index("ix_conversations_participant_b", table_name="conversations")
    op.drop_index("ix_conversations_participant_a", table_name="conversations")
    op.drop_constraint("fk_conversations_participant_b_users", "conversations", type_="foreignkey")
    op.drop_constraint("fk_conversations_participant_a_users", "conversations", type_="foreignkey")
    op.drop_column("conversations", "source_id")
    op.drop_column("conversations", "source_type")
    op.drop_column("conversations", "participant_b")
    op.drop_column("conversations", "participant_a")

    op.drop_index("ix_invitations_status", table_name="invitations")
    op.drop_index("ix_invitations_caregiver_id", table_name="invitations")
    op.drop_index("ix_invitations_patient_id", table_name="invitations")
    op.drop_table("invitations")

    op.drop_index("ix_job_postings_city", table_name="job_postings")
    op.drop_index("ix_job_postings_status", table_name="job_postings")
    op.drop_index("ix_job_postings_patient_id", table_name="job_postings")
    op.drop_constraint("fk_job_postings_patient_id_users", "job_postings", type_="foreignkey")
    op.drop_column("job_postings", "special_requirements")
    op.drop_column("job_postings", "salary")
    op.drop_column("job_postings", "schedule")
    op.drop_column("job_postings", "location")
    op.drop_column("job_postings", "care_type")
    op.drop_column("job_postings", "patient_id")
