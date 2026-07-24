"""add recruitment recommendation interactions

Revision ID: 20260723_0005
Revises: 20260705_0004
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0005"
down_revision: str | None = "20260705_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recruitment_interactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "patient_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "caregiver_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("job_postings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("action_weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("model_version", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_recruitment_interactions_patient_created",
        "recruitment_interactions",
        ["patient_id", "created_at"],
    )
    op.create_index(
        "ix_recruitment_interactions_caregiver_created",
        "recruitment_interactions",
        ["caregiver_id", "created_at"],
    )
    op.create_index(
        "ix_recruitment_interactions_job_created",
        "recruitment_interactions",
        ["job_id", "created_at"],
    )
    op.create_index(
        "ix_recruitment_interactions_action_created",
        "recruitment_interactions",
        ["action_type", "created_at"],
    )
    op.create_index(
        "ix_recruitment_interactions_request_id",
        "recruitment_interactions",
        ["request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recruitment_interactions_request_id",
        table_name="recruitment_interactions",
    )
    op.drop_index(
        "ix_recruitment_interactions_action_created",
        table_name="recruitment_interactions",
    )
    op.drop_index(
        "ix_recruitment_interactions_job_created",
        table_name="recruitment_interactions",
    )
    op.drop_index(
        "ix_recruitment_interactions_caregiver_created",
        table_name="recruitment_interactions",
    )
    op.drop_index(
        "ix_recruitment_interactions_patient_created",
        table_name="recruitment_interactions",
    )
    op.drop_table("recruitment_interactions")
