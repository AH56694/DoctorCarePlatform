"""add recruitment phase zero idempotency constraints

Revision ID: 20260724_0006
Revises: 20260723_0005
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0006"
down_revision: str | None = "20260723_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_applications_job_caregiver",
        "applications",
        ["job_id", "caregiver_id"],
    )
    op.create_unique_constraint(
        "uq_applications_idempotency_key",
        "applications",
        ["idempotency_key"],
    )
    op.add_column(
        "invitations",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_invitations_idempotency_key",
        "invitations",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_invitations_idempotency_key",
        "invitations",
        type_="unique",
    )
    op.drop_column("invitations", "idempotency_key")
    op.drop_constraint(
        "uq_applications_idempotency_key",
        "applications",
        type_="unique",
    )
    op.drop_constraint(
        "uq_applications_job_caregiver",
        "applications",
        type_="unique",
    )
    op.drop_column("applications", "idempotency_key")
