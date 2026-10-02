"""Care chat identity, ordered messages and durable retry keys.

Run with chat writes stopped. MySQL DDL is not transactional: every additive
schema operation checks for previous completion so an interrupted upgrade can
be resumed while writes remain stopped. See docs/聊天并发整改与迁移.md.
"""

import hashlib
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20261002_mysql_0002"
down_revision = "20260905_mysql_0001"
branch_labels = None
depends_on = None


def _conversation_key(row):
    """Freeze this identity algorithm in the migration, independent of app code."""
    participants = (row["participant_a"], row["participant_b"])
    if not all(participants) or participants[0] == participants[1]:
        raise RuntimeError("Care chat migration: repair missing/identical participants before retrying")
    source_type = row["source_type"] or ""
    if source_type in ("", "profile"):
        scope_type, scope_id = "direct", ""
    elif source_type in ("job", "application", "invitation") and row["source_id"]:
        scope_type, scope_id = source_type, row["source_id"]
    else:
        raise RuntimeError("Care chat migration: repair unknown source types or missing source IDs before retrying")
    identity = ["care_chat", *sorted(participants), scope_type, scope_id]
    encoded = json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _merge_plan(conversations, reviews):
    """Validate all groups before changing schema or moving any business rows."""
    groups = {}
    for row in conversations:
        if row["kind"] == "care_chat":
            groups.setdefault(_conversation_key(row), []).append(row)
    canonical = {}
    keys = {}
    for key, rows in groups.items():
        rows.sort(key=lambda row: (row["created_at"], row["id"]))
        winner = rows[0]["id"]
        keys[winner] = key
        for row in rows:
            canonical[row["id"]] = winner
    seen = set()
    for row in reviews:
        pair = (canonical.get(row["conversation_id"], row["conversation_id"]), row["reviewer_id"])
        if pair in seen:
            raise RuntimeError(
                "Care chat migration: duplicate reviewer across conversations to merge; "
                "resolve and archive the conflicting reviews explicitly before retrying"
            )
        seen.add(pair)
    return canonical, keys


def _move_duplicate_data(connection, canonical, keys):
    for old_id, new_id in canonical.items():
        if old_id == new_id:
            continue
        params = {"old_id": old_id, "new_id": new_id}
        # Retain application timestamps despite MySQL's ON UPDATE clauses.
        for table in ("messages", "reviews"):
            connection.execute(sa.text(
                f"UPDATE {table} SET conversation_id=:new_id, updated_at=updated_at "
                "WHERE conversation_id=:old_id"
            ), params)
        connection.execute(sa.text(
            "UPDATE conversation_aliases SET canonical_id=:new_id WHERE canonical_id=:old_id"
        ), params)
        existing = connection.execute(sa.text(
            "SELECT canonical_id FROM conversation_aliases WHERE alias_id=:old_id"
        ), params).scalar_one_or_none()
        if existing is None:
            connection.execute(sa.text(
                "INSERT INTO conversation_aliases (alias_id, canonical_id) VALUES (:old_id, :new_id)"
            ), params)
        elif existing != new_id:
            raise RuntimeError("Care chat migration: conflicting conversation alias; restore/repair before retrying")
        connection.execute(sa.text("DELETE FROM conversations WHERE id=:old_id"), params)
    for conversation_id, key in keys.items():
        connection.execute(sa.text(
            "UPDATE conversations SET conversation_key=:key, updated_at=updated_at WHERE id=:id"
        ), {"id": conversation_id, "key": key})


def _backfill_message_sequences(connection):
    # The temporary table avoids loading message history into the Python process.
    # CREATE/DROP TEMPORARY TABLE do not implicitly commit MySQL transactions.
    connection.execute(sa.text("DROP TEMPORARY TABLE IF EXISTS care_chat_seq_backfill"))
    connection.execute(sa.text(
        "CREATE TEMPORARY TABLE care_chat_seq_backfill ("
        "id CHAR(36) PRIMARY KEY, seq BIGINT NOT NULL) "
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci"
    ))
    try:
        connection.execute(sa.text(
            "INSERT INTO care_chat_seq_backfill (id, seq) "
            "SELECT id, ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY created_at, id) "
            "FROM messages"
        ))
        connection.execute(sa.text(
            "UPDATE messages AS m JOIN care_chat_seq_backfill AS b ON b.id=m.id "
            "SET m.seq=b.seq, m.updated_at=m.updated_at"
        ))
        connection.execute(sa.text(
            "UPDATE conversations AS c LEFT JOIN ("
            "SELECT conversation_id, MAX(seq) AS last_seq, MAX(created_at) AS last_message_at "
            "FROM messages GROUP BY conversation_id) AS m ON m.conversation_id=c.id "
            "SET c.last_seq=COALESCE(m.last_seq, 0), "
            "c.last_message_at=COALESCE(m.last_message_at, c.created_at), c.updated_at=c.updated_at"
        ))
    finally:
        connection.execute(sa.text("DROP TEMPORARY TABLE IF EXISTS care_chat_seq_backfill"))


def _add_missing_columns(connection, table_name, columns):
    existing = {column["name"] for column in sa.inspect(connection).get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _add_missing_index(connection, table_name, name, columns, *, unique=False):
    existing = {index["name"]: index for index in sa.inspect(connection).get_indexes(table_name)}
    if name in existing:
        index = existing[name]
        if index["column_names"] != columns or bool(index["unique"]) != unique:
            raise RuntimeError(f"Care chat migration: incompatible existing index {name}")
        return
    op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "mysql" or op.get_context().as_sql:
        raise RuntimeError("Care chat migration requires an online MySQL 8.4 connection and stopped writes")
    conversations = connection.execute(sa.text(
        "SELECT id, participant_a, participant_b, kind, source_type, source_id, created_at FROM conversations"
    )).mappings().all()
    reviews = connection.execute(sa.text("SELECT conversation_id, reviewer_id FROM reviews")).mappings().all()
    canonical, keys = _merge_plan(conversations, reviews)

    _add_missing_columns(connection, "conversations", [
        sa.Column("conversation_key", sa.String(64), nullable=True),
        sa.Column("last_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_message_at", mysql.DATETIME(fsp=6), nullable=True),
    ])
    _add_missing_columns(connection, "messages", [
        sa.Column("client_message_id", sa.String(36), nullable=True),
        sa.Column("seq", sa.BigInteger(), nullable=True),
    ])
    if "conversation_aliases" not in sa.inspect(connection).get_table_names():
        op.create_table(
            "conversation_aliases",
            sa.Column("alias_id", sa.CHAR(36), primary_key=True),
            sa.Column("canonical_id", sa.CHAR(36), nullable=False),
            sa.ForeignKeyConstraint(
                ["canonical_id"], ["conversations.id"],
                name="fk_conversation_aliases_canonical_id", ondelete="CASCADE",
            ),
            mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci",
        )

    # No DDL inside this block: moving reviews/messages, aliases and watermarks
    # either finish together or are rolled back on a data error. The first DDL
    # below commits successful DML as required by MySQL's implicit-commit rules.
    _move_duplicate_data(connection, canonical, keys)
    _backfill_message_sequences(connection)
    if connection.execute(sa.text("SELECT COUNT(*) FROM messages WHERE seq IS NULL OR seq < 1")).scalar_one():
        raise RuntimeError("Care chat migration: sequence validation failed")

    columns = {column["name"]: column for column in sa.inspect(connection).get_columns("messages")}
    if columns["seq"]["nullable"]:
        op.alter_column("messages", "seq", existing_type=sa.BigInteger(), nullable=False)
    _add_missing_index(connection, "conversations", "uq_conversations_key", ["conversation_key"], unique=True)
    _add_missing_index(connection, "conversations", "ix_conversations_a_activity", ["participant_a", "last_message_at", "id"])
    _add_missing_index(connection, "conversations", "ix_conversations_b_activity", ["participant_b", "last_message_at", "id"])
    _add_missing_index(connection, "messages", "uq_messages_client_id", ["conversation_id", "sender_id", "client_message_id"], unique=True)
    _add_missing_index(connection, "messages", "uq_messages_conversation_seq", ["conversation_id", "seq"], unique=True)
    _add_missing_index(connection, "conversation_aliases", "ix_conversation_aliases_canonical_id", ["canonical_id"])


def downgrade():
    raise RuntimeError("Conversation merging is irreversible. Restore a verified full backup with writes stopped.")
