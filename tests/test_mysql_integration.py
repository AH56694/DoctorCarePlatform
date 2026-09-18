"""Run against an isolated CI database after the MySQL migration job."""

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.app.db.models import Base

pytestmark = pytest.mark.skipif(not os.getenv("TEST_MYSQL_URL"), reason="requires isolated MySQL")


def test_mysql_baseline_matches_application_columns_and_unique_constraints():
    engine = create_engine(os.environ["TEST_MYSQL_URL"])
    try:
        inspector = inspect(engine)
        for table in Base.metadata.sorted_tables:
            expected = {column.name for column in table.columns}
            actual = {column["name"] for column in inspector.get_columns(table.name)}
            assert expected <= actual, f"Missing columns on {table.name}: {expected - actual}"
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20260905_mysql_0001"
            transaction = connection.get_transaction()
            connection.execute(text("INSERT INTO users (id, phone) VALUES (:id, :phone)"), {
                "id": "integration-user-1", "phone": "integration-phone",
            })
            with pytest.raises(IntegrityError):
                connection.execute(text("INSERT INTO users (id, phone) VALUES (:id, :phone)"), {
                    "id": "integration-user-2", "phone": "integration-phone",
                })
            transaction.rollback()
    finally:
        engine.dispose()
