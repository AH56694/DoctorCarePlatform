"""Frozen MySQL baseline; the historical PostgreSQL chain remains unchanged."""

import re
from pathlib import Path

from alembic import op
from sqlalchemy import inspect

revision = "20260905_mysql_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "mysql":
        raise RuntimeError("This baseline requires MySQL 8.4")
    schema = (Path(__file__).parent / "20260905_baseline.sql").read_text(encoding="utf-8")
    baseline_tables = set(re.findall(r"CREATE TABLE (\w+)", schema))
    if not op.get_context().as_sql:
        existing = baseline_tables.intersection(inspect(connection).get_table_names())
        if existing:
            raise RuntimeError(
                "Existing business tables detected. Back up and compare the schema before "
                "adopting this baseline; never stamp an unverified database."
            )
    for statement in schema.split(";"):
        if statement.strip():
            op.execute(statement.strip())


def downgrade():
    raise RuntimeError("Baseline downgrade is destructive. Restore a verified backup instead.")
