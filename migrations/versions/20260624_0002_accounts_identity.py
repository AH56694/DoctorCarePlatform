"""accounts and identity module

Revision ID: 20260624_0002
Revises: 20260624_0001
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260624_0002"
down_revision: str | None = "20260624_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("users", sa.Column("active_role", sa.String(length=32), nullable=False, server_default="patient"))
    op.add_column("user_roles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_unique_constraint("uq_user_roles_user_role", "user_roles", ["user_id", "role"])

    op.create_table(
        "patient_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("real_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("id_number", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("id_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("basic_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_patient_profiles_user_id", "patient_profiles", ["user_id"])

    op.create_table(
        "caregiver_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("real_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("id_number", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("id_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("experience_years", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("service_city", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("rating_avg", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_caregiver_profiles_user_id", "caregiver_profiles", ["user_id"])

    op.create_table(
        "certifications",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "caregiver_profile_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("caregiver_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("certificate_type", sa.String(length=80), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_certifications_review_status", "certifications", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_certifications_review_status", table_name="certifications")
    op.drop_table("certifications")
    op.drop_constraint("uq_caregiver_profiles_user_id", "caregiver_profiles", type_="unique")
    op.drop_table("caregiver_profiles")
    op.drop_constraint("uq_patient_profiles_user_id", "patient_profiles", type_="unique")
    op.drop_table("patient_profiles")
    op.drop_constraint("uq_user_roles_user_role", "user_roles", type_="unique")
    op.drop_column("user_roles", "is_active")
    op.drop_column("users", "active_role")
    op.drop_column("users", "password_hash")
