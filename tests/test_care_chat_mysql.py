"""Committed concurrency tests for an explicitly configured, migrated test MySQL.

Set TEST_MYSQL_URL to a disposable database whose name contains ``test`` or ends
with ``_ci``. This suite never creates/drops schemas and deletes only its UUID
fixtures. Do not point it at a development or production database containing
valuable data. SQLite cannot validate the locking guarantees asserted here.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.db.models import Conversation, ConversationAlias, JobPosting, Message, User
from backend.app.services.care_chat import get_or_create_conversation, send_message

pytestmark = pytest.mark.skipif(not os.getenv("TEST_MYSQL_URL"), reason="requires isolated MySQL")


@pytest.fixture
def mysql_chat():
    url = make_url(os.environ["TEST_MYSQL_URL"])
    database_name = (url.database or "").lower()
    if (
        url.get_backend_name() != "mysql"
        or not ("test" in database_name or database_name.endswith("_ci"))
        or settings.is_production
    ):
        pytest.fail(
            "Care-chat concurrency tests require a named test/_ci MySQL and non-production APP_ENV"
        )
    engine = create_engine(
        url,
        pool_size=20,
        max_overflow=5,
        pool_timeout=20,
        isolation_level="REPEATABLE READ",
        connect_args={"connect_timeout": 5, "read_timeout": 30, "write_timeout": 30},
    )
    inspector = inspect(engine)
    required = {
        "conversations": {"last_seq", "last_message_at"},
        "messages": {"seq", "client_message_id"},
        "conversation_aliases": {"alias_id", "canonical_id"},
    }
    for table, columns in required.items():
        assert inspector.has_table(table), f"Run the care-chat migration: missing {table}"
        assert columns <= {column["name"] for column in inspector.get_columns(table)}, (
            f"Run the care-chat migration: incomplete {table}"
        )
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    run_id = uuid4().hex[:10]
    user_ids = [str(uuid4()), str(uuid4())]
    job_id = str(uuid4())
    with factory() as db:
        db.add_all(
            [
                User(id=user_id, phone=f"cc-{run_id}-{index}", status="active")
                for index, user_id in enumerate(user_ids)
            ]
        )
        db.flush()
        db.add(JobPosting(id=job_id, employer_id=user_ids[0], title="Concurrency fixture"))
        db.commit()
    try:
        yield factory, user_ids, job_id
    finally:
        # Every worker has completed before fixture teardown. Restrict cleanup to
        # conversations owned by this invocation's two randomly generated users.
        with factory() as db:
            conversation_ids = list(
                db.scalars(select(Conversation.id).where(Conversation.owner_id.in_(user_ids)))
            )
            if conversation_ids:
                db.execute(
                    delete(ConversationAlias).where(
                        ConversationAlias.canonical_id.in_(conversation_ids)
                    )
                )
                db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
                db.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))
            db.execute(delete(JobPosting).where(JobPosting.id == job_id))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()
        engine.dispose()


def make_conversation(factory, users):
    with factory() as db:
        conversation, _ = get_or_create_conversation(
            db,
            owner_id=users[0],
            participant_a=users[0],
            participant_b=users[1],
        )
        db.commit()
        return conversation.id


def test_mysql_100_same_key_sends_create_one_message(mysql_chat):
    factory, users, _ = mysql_chat
    conversation_id = make_conversation(factory, users)
    key = str(uuid4())

    def attempt(_):
        with factory() as db:
            message, created = send_message(
                db,
                conversation_id=conversation_id,
                sender_id=users[0],
                client_message_id=key,
                body="one logical message",
            )
            return message.id, message.seq, created

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(attempt, range(100)))
    assert len({item[0] for item in results}) == 1
    assert {item[1] for item in results} == {1}
    assert sum(item[2] for item in results) == 1
    with factory() as db:
        assert db.query(Message).filter_by(conversation_id=conversation_id).count() == 1
        assert db.get(Conversation, conversation_id).last_seq == 1


def test_mysql_concurrent_reversed_pairs_create_one_conversation(mysql_chat):
    factory, users, _ = mysql_chat

    def attempt(index):
        first, second = users if index % 2 else list(reversed(users))
        with factory() as db:
            conversation, created = get_or_create_conversation(
                db,
                owner_id=first,
                participant_a=first,
                participant_b=second,
                source_type="profile" if index % 3 else "",
                source_id=second if index % 3 else None,
            )
            db.commit()
            return conversation.id, created

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(attempt, range(100)))
    assert len({item[0] for item in results}) == 1
    assert sum(item[1] for item in results) == 1
    with factory() as db:
        assert db.query(Conversation).filter(Conversation.owner_id.in_(users)).count() == 1


def test_mysql_1000_concurrent_messages_have_gapless_sequence_pagination(mysql_chat):
    factory, users, _ = mysql_chat
    conversation_id = make_conversation(factory, users)

    def attempt(index):
        with factory() as db:
            message, created = send_message(
                db,
                conversation_id=conversation_id,
                sender_id=users[index % 2],
                client_message_id=str(uuid4()),
                body=f"load-fixture-{index}",
            )
            assert created
            return message.seq

    with ThreadPoolExecutor(max_workers=20) as executor:
        sequences = list(executor.map(attempt, range(1000)))
    assert sorted(sequences) == list(range(1, 1001))
    seen = []
    with factory() as db:
        while True:
            batch = list(
                db.scalars(
                    select(Message.seq)
                    .where(
                        Message.conversation_id == conversation_id,
                        Message.seq > (seen[-1] if seen else 0),
                    )
                    .order_by(Message.seq)
                    .limit(73)
                )
            )
            if not batch:
                break
            seen.extend(batch)
        assert db.get(Conversation, conversation_id).last_seq == 1000
    assert seen == list(range(1, 1001))


def test_mysql_next_sequence_cannot_commit_ahead_of_the_locked_predecessor(mysql_chat):
    factory, users, _ = mysql_chat
    conversation_id = make_conversation(factory, users)
    entered = Event()
    finished = Event()

    def second_writer():
        entered.set()
        with factory() as db:
            message, _ = send_message(
                db,
                conversation_id=conversation_id,
                sender_id=users[1],
                client_message_id=str(uuid4()),
                body="second commit",
            )
            finished.set()
            return message.seq

    with factory() as first:
        conversation = first.scalar(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
            )
            .with_for_update()
        )
        conversation.last_seq = 1
        first.add(
            Message(
                conversation_id=conversation_id,
                sender_id=users[0],
                sender_type="user",
                client_message_id=str(uuid4()),
                seq=1,
                body="first commit",
                content="first commit",
            )
        )
        first.flush()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second_writer)
            try:
                assert entered.wait(5)
                assert not finished.wait(0.2), (
                    "Second sender bypassed the per-conversation row lock"
                )
                with factory() as reader:
                    assert reader.get(Conversation, conversation_id).last_seq == 0
                    assert (
                        reader.query(Message).filter_by(conversation_id=conversation_id).count()
                        == 0
                    )
            finally:
                # Release even on a failed assertion so the worker cannot hang teardown.
                first.commit()
            assert future.result(timeout=20) == 2
    with factory() as reader:
        assert list(
            reader.scalars(
                select(Message.seq)
                .where(
                    Message.conversation_id == conversation_id,
                )
                .order_by(Message.seq)
            )
        ) == [1, 2]


def test_mysql_stale_snapshot_duplicate_does_not_rollback_the_outer_job_transaction(mysql_chat):
    factory, users, job_id = mysql_chat
    source_id = str(uuid4())
    with factory() as outer:
        job = outer.get(JobPosting, job_id)  # Start a repeatable-read snapshot.
        assert (
            outer.execute(text("SELECT @@transaction_isolation")).scalar_one() == "REPEATABLE-READ"
        )
        with factory() as winner:
            existing, _ = get_or_create_conversation(
                winner,
                owner_id=users[0],
                participant_a=users[0],
                participant_b=users[1],
                source_type="application",
                source_id=source_id,
            )
            winner.commit()
            winner_id = existing.id
        job.status = "matched"
        reused, created = get_or_create_conversation(
            outer,
            owner_id=users[0],
            participant_a=users[0],
            participant_b=users[1],
            source_type="application",
            source_id=source_id,
        )
        assert not created
        assert reused.id == winner_id
        outer.commit()
    with factory() as check:
        assert check.get(JobPosting, job_id).status == "matched"
        assert check.query(Conversation).filter_by(source_id=source_id).count() == 1


def test_mysql_get_or_create_does_not_commit_the_callers_transaction(mysql_chat):
    factory, users, job_id = mysql_chat
    with factory() as outer:
        job = outer.get(JobPosting, job_id)
        job.status = "matched"
        conversation, created = get_or_create_conversation(
            outer,
            owner_id=users[0],
            participant_a=users[0],
            participant_b=users[1],
            source_type="job",
            source_id=job_id,
        )
        assert created
        conversation_id = conversation.id
        outer.rollback()
    with factory() as check:
        assert check.get(JobPosting, job_id).status == "draft"
        assert check.get(Conversation, conversation_id) is None
