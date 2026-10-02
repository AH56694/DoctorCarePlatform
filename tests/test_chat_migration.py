"""Exercise merge decisions without requiring a MySQL service."""

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations/mysql_versions/20261002_0002_care_chat.py"
spec = importlib.util.spec_from_file_location("care_chat_migration", MIGRATION_PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def conversation(id="first", **overrides):
    return {
        "id": id, "participant_a": "alice", "participant_b": "bob", "kind": "care_chat",
        "source_type": "", "source_id": None, "created_at": datetime(2026, 1, 1), **overrides,
    }


def test_migration_identity_normalizes_direct_sources_but_preserves_business_scope():
    direct = migration._conversation_key(conversation())
    assert direct == migration._conversation_key(conversation(
        participant_a="bob", participant_b="alice", source_type="profile", source_id="ignored",
    ))
    scopes = [migration._conversation_key(conversation(source_type=kind, source_id="business-id"))
              for kind in ("job", "application", "invitation")]
    assert len({direct, *scopes}) == 4


def test_migration_identity_matches_the_runtime_algorithm():
    from backend.app.services.care_chat import conversation_key

    for source_type, source_id in (("", None), ("profile", "ignored"), ("job", "job-id"),
                                   ("application", "application-id"), ("invitation", "invitation-id")):
        row = conversation(source_type=source_type, source_id=source_id)
        assert migration._conversation_key(row) == conversation_key("alice", "bob", source_type, source_id)


@pytest.mark.parametrize("overrides", [
    {"participant_a": None}, {"participant_a": "bob"}, {"source_type": "unsupported"},
    {"source_type": "job", "source_id": None},
])
def test_migration_rejects_ambiguous_legacy_identity(overrides):
    with pytest.raises(RuntimeError, match="before retrying"):
        migration._conversation_key(conversation(**overrides))


def test_migration_merge_is_deterministic_and_does_not_change_initiator():
    original = conversation("original", participant_a="bob", participant_b="alice")
    duplicate = conversation("duplicate", source_type="profile", created_at=original["created_at"] + timedelta(seconds=1))
    unrelated = conversation("ai", kind="ai_chat", participant_b=None)
    canonical, keys = migration._merge_plan([duplicate, unrelated, original], [])
    assert canonical == {"original": "original", "duplicate": "original"}
    assert list(keys) == ["original"]
    assert original["participant_a"] == "bob"


def test_migration_blocks_review_conflicts_before_any_data_move():
    with pytest.raises(RuntimeError, match="duplicate reviewer"):
        migration._merge_plan([conversation("one"), conversation("two")], [
            {"conversation_id": "one", "reviewer_id": "alice"},
            {"conversation_id": "two", "reviewer_id": "alice"},
        ])


def test_migration_moves_messages_reviews_and_aliases_without_losing_ids():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for statement in (
            "CREATE TABLE conversations (id TEXT PRIMARY KEY, conversation_key TEXT, updated_at TEXT)",
            "CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT, updated_at TEXT)",
            "CREATE TABLE reviews (id TEXT PRIMARY KEY, conversation_id TEXT, updated_at TEXT)",
            "CREATE TABLE conversation_aliases (alias_id TEXT PRIMARY KEY, canonical_id TEXT)",
        ):
            connection.execute(text(statement))
        connection.execute(text("INSERT INTO conversations (id, updated_at) VALUES ('original', 'kept'), ('duplicate', 'kept')"))
        connection.execute(text("INSERT INTO messages VALUES ('message-id', 'duplicate', 'kept')"))
        connection.execute(text("INSERT INTO reviews VALUES ('review-id', 'duplicate', 'kept')"))
        connection.execute(text("INSERT INTO conversation_aliases VALUES ('older-alias', 'duplicate')"))
        canonical, keys = migration._merge_plan([
            conversation("original"), conversation("duplicate", created_at=datetime(2026, 1, 2)),
        ], [{"conversation_id": "duplicate", "reviewer_id": "alice"}])
        migration._move_duplicate_data(connection, canonical, keys)
        migration._move_duplicate_data(connection, canonical, keys)
        assert connection.execute(text("SELECT id FROM conversations")).scalars().all() == ["original"]
        assert connection.execute(text("SELECT * FROM messages")).one() == ("message-id", "original", "kept")
        assert connection.execute(text("SELECT * FROM reviews")).one() == ("review-id", "original", "kept")
        aliases = dict(connection.execute(text("SELECT alias_id, canonical_id FROM conversation_aliases")).all())
        assert aliases == {"older-alias": "original", "duplicate": "original"}
    engine.dispose()
