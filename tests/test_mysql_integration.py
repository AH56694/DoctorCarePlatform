"""Run against an isolated CI database after the MySQL migration job."""

import os
from datetime import datetime
import importlib.util
from pathlib import Path

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
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261002_mysql_0002"
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


def test_mysql_chat_indexes_and_sequence_constraints():
    engine = create_engine(os.environ["TEST_MYSQL_URL"])
    try:
        inspector = inspect(engine)
        expected_indexes = {
            "conversations": {
                "uq_conversations_key": (["conversation_key"], True),
                "ix_conversations_a_activity": (["participant_a", "last_message_at", "id"], False),
                "ix_conversations_b_activity": (["participant_b", "last_message_at", "id"], False),
            },
            "messages": {
                "uq_messages_conversation_seq": (["conversation_id", "seq"], True),
                "uq_messages_client_id": (["conversation_id", "sender_id", "client_message_id"], True),
            },
        }
        for table_name, expected in expected_indexes.items():
            indexes = {index["name"]: index for index in inspector.get_indexes(table_name)}
            for name, (columns, unique) in expected.items():
                assert indexes[name]["column_names"] == columns
                assert bool(indexes[name]["unique"]) == unique
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("INSERT INTO users (id, phone) VALUES ('chat-integration-user', 'chat-integration-phone')"))
                connection.execute(text(
                    "INSERT INTO conversations (id, owner_id, conversation_key) "
                    "VALUES ('chat-integration-conversation', 'chat-integration-user', :key)"
                ), {"key": "f" * 64})
                insert_message = text(
                    "INSERT INTO messages (id, conversation_id, sender_id, client_message_id, seq, body) "
                    "VALUES (:id, 'chat-integration-conversation', 'chat-integration-user', :client_id, :seq, 'test')"
                )
                connection.execute(insert_message, {"id": "chat-message-1", "client_id": "retry-1", "seq": 1})
                with pytest.raises(IntegrityError):
                    connection.execute(insert_message, {"id": "chat-message-2", "client_id": "retry-1", "seq": 2})
                with pytest.raises(IntegrityError):
                    connection.execute(insert_message, {"id": "chat-message-3", "client_id": "retry-2", "seq": 1})
                # v1 clients have no retry key; NULL must not block distinct sends.
                connection.execute(insert_message, {"id": "chat-message-4", "client_id": None, "seq": 2})
                connection.execute(insert_message, {"id": "chat-message-5", "client_id": None, "seq": 3})
                with pytest.raises(IntegrityError):
                    connection.execute(text(
                        "INSERT INTO conversations (id, owner_id, conversation_key) "
                        "VALUES ('chat-integration-duplicate', 'chat-integration-user', :key)"
                    ), {"key": "f" * 64})
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_mysql_chat_migration_moves_legacy_history_and_backfills_committed_order():
    path = Path(__file__).resolve().parents[1] / "migrations/mysql_versions/20261002_0002_care_chat.py"
    spec = importlib.util.spec_from_file_location("mysql_care_chat_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(os.environ["TEST_MYSQL_URL"])
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(
                    "INSERT INTO users (id, phone) VALUES "
                    "('chat-migration-alice', 'chat-migration-alice'), ('chat-migration-bob', 'chat-migration-bob')"
                ))
                connection.execute(text(
                    "INSERT INTO conversations (id, owner_id, participant_a, participant_b, source_type, created_at) "
                    "VALUES (:id, 'chat-migration-alice', 'chat-migration-alice', 'chat-migration-bob', :source, :created)"
                ), [
                    {"id": "chat-migration-main", "source": "", "created": datetime(2026, 1, 1)},
                    {"id": "chat-migration-old", "source": "profile", "created": datetime(2026, 1, 2)},
                ])
                connection.execute(text(
                    "INSERT INTO messages (id, conversation_id, sender_id, seq, body, created_at) "
                    "VALUES (:id, :conversation, 'chat-migration-alice', :seq, 'migration-test', :created)"
                ), [
                    {"id": "chat-migration-a", "conversation": "chat-migration-main", "seq": 100, "created": datetime(2026, 1, 3)},
                    {"id": "chat-migration-b", "conversation": "chat-migration-old", "seq": 200, "created": datetime(2026, 1, 3)},
                    {"id": "chat-migration-c", "conversation": "chat-migration-old", "seq": 300, "created": datetime(2026, 1, 4)},
                ])
                connection.execute(text(
                    "INSERT INTO reviews (id, conversation_id, reviewer_id, reviewee_id, score) "
                    "VALUES ('chat-migration-review', 'chat-migration-old', 'chat-migration-bob', 'chat-migration-alice', 5)"
                ))
                rows = connection.execute(text(
                    "SELECT id, participant_a, participant_b, kind, source_type, source_id, created_at "
                    "FROM conversations WHERE id IN ('chat-migration-main', 'chat-migration-old')"
                )).mappings().all()
                canonical, keys = migration._merge_plan(rows, [
                    {"conversation_id": "chat-migration-old", "reviewer_id": "chat-migration-bob"},
                ])
                migration._move_duplicate_data(connection, canonical, keys)
                migration._backfill_message_sequences(connection)
                assert connection.execute(text(
                    "SELECT id, seq FROM messages WHERE conversation_id='chat-migration-main' ORDER BY seq"
                )).all() == [("chat-migration-a", 1), ("chat-migration-b", 2), ("chat-migration-c", 3)]
                assert connection.execute(text(
                    "SELECT last_seq, last_message_at FROM conversations WHERE id='chat-migration-main'"
                )).one() == (3, datetime(2026, 1, 4))
                assert connection.execute(text(
                    "SELECT canonical_id FROM conversation_aliases WHERE alias_id='chat-migration-old'"
                )).scalar_one() == "chat-migration-main"
                assert connection.execute(text(
                    "SELECT conversation_id FROM reviews WHERE id='chat-migration-review'"
                )).scalar_one() == "chat-migration-main"
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
