"""Public care-chat contracts, with real auth and an isolated SQLite database.

These tests verify pagination and retry behavior, not MySQL lock scheduling. The
separate test_care_chat_mysql.py suite covers committed concurrent transactions.
"""

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from threading import BoundedSemaphore
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.db.models import Base, Conversation, ConversationAlias, Message, User, UserRole
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services import care_chat_admission
from backend.app.services.auth import issue_access_token
from backend.app.services.care_chat import get_or_create_conversation, send_message
from backend.app.services.care_chat_cache import latest_page_cache


class MemoryRedis:
    """Exercise cache serialization and keying without contacting a real Redis."""

    def __init__(self):
        self.values = {}
        self.get_calls = 0
        self.failed = False

    def get(self, key):
        self.get_calls += 1
        if self.failed:
            raise RedisConnectionError("simulated Redis outage")
        return self.values.get(key)

    def set(self, key, value, **kwargs):
        if self.failed:
            raise RedisConnectionError("simulated Redis outage")
        self.values[key] = value
        return True


@pytest.fixture
def chat_api(monkeypatch):
    # Production-mode validation/Redis health checks belong to other tests.
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "care_chat_cache_enabled", True)
    monkeypatch.setattr(settings, "care_chat_send_rate", 100)
    monkeypatch.setattr(settings, "care_chat_send_burst", 200)
    monkeypatch.setattr(settings, "care_chat_legacy_send_enabled", True)
    monkeypatch.setattr(care_chat_admission._redis, "eval", lambda *args: 0)
    monkeypatch.setattr(care_chat_admission, "_redis_retry_at", 0.0)
    monkeypatch.setattr(care_chat_admission, "_buckets", OrderedDict())
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    app = create_app()

    def database():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    cache = MemoryRedis()
    monkeypatch.setattr(latest_page_cache, "client", cache)
    monkeypatch.setattr(latest_page_cache, "_retry_at", 0.0)
    with factory() as db:
        users = {}
        for name in ("owner", "peer", "stranger"):
            user = User(phone=f"v2-{name}", active_role="patient", status="active")
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role="patient", is_active=True))
            users[name] = user.id
        db.commit()
        conversation, _ = get_or_create_conversation(
            db,
            owner_id=users["owner"],
            participant_a=users["owner"],
            participant_b=users["peer"],
            title="Test conversation",
        )
        db.commit()
        conversation_id = conversation.id
    with TestClient(app) as client:
        yield client, factory, users, conversation_id, cache
    app.dependency_overrides.clear()
    engine.dispose()


def auth(user_id):
    return {"Authorization": f"Bearer {issue_access_token(user_id)}"}


def messages_url(conversation_id):
    return f"/api/v2/conversations/{conversation_id}/messages"


def send(client, users, conversation_id, **changes):
    payload = {"client_message_id": str(uuid4()), "body": "护理沟通"}
    payload.update(changes)
    return client.post(messages_url(conversation_id), headers=auth(users["owner"]), json=payload)


def seed_messages(factory, conversation_id, sender_id, count):
    # Deliberately give every message the same timestamp: ordering must use seq.
    stamp = datetime(2026, 1, 1, 0, 0)
    with factory() as db:
        conversation = db.get(Conversation, conversation_id)
        start = conversation.last_seq
        db.add_all(
            [
                Message(
                    conversation_id=conversation_id,
                    sender_id=sender_id,
                    sender_type="user",
                    client_message_id=str(uuid4()),
                    seq=seq,
                    body=f"message-{seq}",
                    content=f"message-{seq}",
                    created_at=stamp,
                )
                for seq in range(start + 1, start + count + 1)
            ]
        )
        conversation.last_seq = start + count
        conversation.last_message_at = stamp
        db.commit()


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v2/conversations"),
        ("get", "/api/v2/conversations/missing/messages"),
        ("post", "/api/v2/conversations/missing/messages"),
    ],
)
def test_v2_requires_authentication(chat_api, method, path):
    client, *_ = chat_api
    response = client.request(
        method,
        path,
        json={
            "client_message_id": str(uuid4()),
            "body": "hello",
        },
    )
    assert response.status_code == 401


def test_history_and_cache_are_private(chat_api):
    client, _, users, conversation_id, cache = chat_api
    assert send(client, users, conversation_id).status_code == 201
    assert (
        client.get(messages_url(conversation_id), headers=auth(users["owner"])).status_code == 200
    )
    get_calls = cache.get_calls
    response = client.get(messages_url(conversation_id), headers=auth(users["stranger"]))
    assert response.status_code == 403
    assert cache.get_calls == get_calls, "Membership must be checked before cache lookup"
    response = client.post(
        messages_url(conversation_id),
        headers=auth(users["stranger"]),
        json={
            "client_message_id": str(uuid4()),
            "body": "unauthorized",
        },
    )
    assert response.status_code == 403
    listing = client.get("/api/v2/conversations", headers=auth(users["stranger"]))
    assert listing.status_code == 200
    assert listing.json()["items"] == []


def test_send_retry_returns_the_original_message_without_advancing_sequence(chat_api):
    client, factory, users, conversation_id, _ = chat_api
    key = str(uuid4())
    first = send(client, users, conversation_id, client_message_id=key)
    retry = send(client, users, conversation_id, client_message_id=key)
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json() == first.json()
    assert first.json()["sender_id"] == users["owner"]
    assert first.json()["seq"] == 1
    with factory() as db:
        assert db.query(Message).filter_by(conversation_id=conversation_id).count() == 1
        assert db.get(Conversation, conversation_id).last_seq == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"body": "different content"},
        {"attachment_url": "https://example.invalid/changed.png"},
        {"attachment_type": "image/png"},
    ],
)
def test_reused_id_with_different_payload_is_a_conflict(chat_api, changes):
    client, factory, users, conversation_id, _ = chat_api
    key = str(uuid4())
    assert send(client, users, conversation_id, client_message_id=key).status_code == 201
    response = send(client, users, conversation_id, client_message_id=key, **changes)
    assert response.status_code == 409
    with factory() as db:
        assert db.query(Message).filter_by(conversation_id=conversation_id).count() == 1
        assert db.get(Conversation, conversation_id).last_seq == 1


def test_idempotency_keys_are_scoped_to_the_sender(chat_api):
    client, _, users, conversation_id, _ = chat_api
    key = str(uuid4())
    assert send(client, users, conversation_id, client_message_id=key).status_code == 201
    response = client.post(
        messages_url(conversation_id),
        headers=auth(users["peer"]),
        json={
            "client_message_id": key,
            "body": "reply",
        },
    )
    assert response.status_code == 201
    assert response.json()["seq"] == 2
    assert response.json()["sender_id"] == users["peer"]


@pytest.mark.parametrize(
    "payload",
    [
        {"body": "missing retry key"},
        {"client_message_id": "not-a-uuid", "body": "invalid retry key"},
        {"client_message_id": str(uuid4()), "body": ""},
    ],
)
def test_send_validates_the_new_contract(chat_api, payload):
    client, _, users, conversation_id, _ = chat_api
    response = client.post(
        messages_url(conversation_id), headers=auth(users["owner"]), json=payload
    )
    assert response.status_code == 422


def test_latest_then_older_pages_cover_1000_equal_timestamp_messages(chat_api):
    client, factory, users, conversation_id, _ = chat_api
    seed_messages(factory, conversation_id, users["owner"], 1000)
    params = {"limit": 73}
    batches = []
    while True:
        response = client.get(
            messages_url(conversation_id), headers=auth(users["owner"]), params=params
        )
        assert response.status_code == 200
        page = response.json()
        seqs = [message["seq"] for message in page["items"]]
        assert seqs == sorted(seqs)
        batches.append(seqs)
        if not page["has_more"]:
            break
        assert page["older_cursor"]
        assert len(batches) <= 15, "A cursor must advance on every nonempty page"
        params["before"] = page["older_cursor"]
    assert batches[0] == list(range(928, 1001))
    assert [seq for batch in reversed(batches) for seq in batch] == list(range(1, 1001))


def test_incremental_pages_drain_backlog_and_do_not_skip_a_later_commit(chat_api):
    client, factory, users, conversation_id, _ = chat_api
    empty = client.get(messages_url(conversation_id), headers=auth(users["owner"])).json()
    assert empty["items"] == []
    assert empty["sync_cursor"]
    seed_messages(factory, conversation_id, users["owner"], 1000)
    cursor = empty["sync_cursor"]
    collected = []
    for _ in range(16):
        response = client.get(
            messages_url(conversation_id),
            headers=auth(users["owner"]),
            params={
                "after": cursor,
                "limit": 73,
            },
        )
        assert response.status_code == 200
        page = response.json()
        collected.extend(message["seq"] for message in page["items"])
        cursor = page["sync_cursor"]
        if not page["has_more"]:
            break
    assert collected == list(range(1, 1001))
    assert send(client, users, conversation_id, body="after the backlog").status_code == 201
    response = client.get(
        messages_url(conversation_id),
        headers=auth(users["owner"]),
        params={
            "after": cursor,
        },
    )
    assert [message["seq"] for message in response.json()["items"]] == [1001]


def test_message_cursor_is_bound_to_conversation_and_cannot_be_tampered(chat_api):
    client, factory, users, conversation_id, _ = chat_api
    page = client.get(messages_url(conversation_id), headers=auth(users["owner"])).json()
    cursor = page["sync_cursor"]
    with factory() as db:
        second, _ = get_or_create_conversation(
            db,
            owner_id=users["owner"],
            participant_a=users["owner"],
            participant_b=users["peer"],
            source_type="job",
            source_id=str(uuid4()),
        )
        db.commit()
        second_id = second.id
    cases = [
        (second_id, {"after": cursor}),
        (conversation_id, {"after": "x" + cursor}),
        (conversation_id, {"after": cursor, "before": cursor}),
    ]
    for target_id, params in cases:
        response = client.get(messages_url(target_id), headers=auth(users["owner"]), params=params)
        assert response.status_code in (400, 422)


def test_redis_failure_never_loses_persisted_messages(chat_api):
    client, _, users, conversation_id, cache = chat_api
    cache.failed = True
    assert send(client, users, conversation_id, body="Redis is down").status_code == 201
    response = client.get(messages_url(conversation_id), headers=auth(users["owner"]))
    assert response.status_code == 200
    assert [item["body"] for item in response.json()["items"]] == ["Redis is down"]


def test_old_cache_version_and_different_page_size_cannot_hide_messages(chat_api):
    client, _, users, conversation_id, cache = chat_api
    assert send(client, users, conversation_id, body="first").status_code == 201
    first = client.get(
        messages_url(conversation_id), headers=auth(users["owner"]), params={"limit": 1}
    )
    assert first.status_code == 200
    old_values = deepcopy(cache.values)
    assert old_values, "The latest complete page should be cached"
    assert send(client, users, conversation_id, body="second").status_code == 201
    response = client.get(
        messages_url(conversation_id), headers=auth(users["owner"]), params={"limit": 1}
    )
    assert [item["seq"] for item in response.json()["items"]] == [2]
    # A delayed writer restores an older version after the newer page is cached.
    cache.values.update(old_values)
    response = client.get(
        messages_url(conversation_id), headers=auth(users["owner"]), params={"limit": 2}
    )
    assert [item["seq"] for item in response.json()["items"]] == [1, 2]


def test_conversation_key_normalizes_pair_but_preserves_job_scopes(chat_api):
    _, factory, users, conversation_id, _ = chat_api
    with factory() as db:
        reverse, created = get_or_create_conversation(
            db,
            owner_id=users["peer"],
            participant_a=users["peer"],
            participant_b=users["owner"],
            source_type="profile",
            source_id=users["owner"],
        )
        assert not created
        assert reverse.id == conversation_id
        source_id = str(uuid4())
        scoped_ids = []
        for source_type in ("job", "application", "invitation"):
            conversation, created = get_or_create_conversation(
                db,
                owner_id=users["owner"],
                participant_a=users["owner"],
                participant_b=users["peer"],
                source_type=source_type,
                source_id=source_id,
            )
            assert created
            scoped_ids.append(conversation.id)
        db.commit()
    assert len(set(scoped_ids + [conversation_id])) == 4


def test_conversation_list_paginates_without_duplicates_at_timestamp_ties(chat_api):
    client, factory, users, conversation_id, _ = chat_api
    expected = {conversation_id}
    with factory() as db:
        for _ in range(34):
            conversation, _ = get_or_create_conversation(
                db,
                owner_id=users["owner"],
                participant_a=users["owner"],
                participant_b=users["peer"],
                source_type="job",
                source_id=str(uuid4()),
            )
            expected.add(conversation.id)
        for conversation in db.scalars(select(Conversation)):
            conversation.created_at = datetime(2026, 1, 1)
            conversation.updated_at = datetime(2026, 1, 1)
        db.commit()
    seen = []
    params = {"limit": 7}
    for _ in range(6):
        response = client.get("/api/v2/conversations", headers=auth(users["owner"]), params=params)
        assert response.status_code == 200
        page = response.json()
        seen.extend(item["id"] for item in page["items"])
        if not page["has_more"]:
            break
        assert page["next_cursor"]
        params["cursor"] = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 35
    assert set(seen) == expected


def test_service_rejects_nonparticipant_even_outside_the_http_layer(chat_api):
    from fastapi import HTTPException

    _, factory, users, conversation_id, _ = chat_api
    with factory() as db, pytest.raises(HTTPException) as error:
        send_message(
            db,
            conversation_id=conversation_id,
            sender_id=users["stranger"],
            client_message_id=str(uuid4()),
            body="forbidden",
        )
    assert error.value.status_code == 403


def test_v1_message_response_remains_a_list(chat_api):
    client, _, users, conversation_id, _ = chat_api
    assert send(client, users, conversation_id).status_code == 201
    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"user_id": users["owner"]},
        headers=auth(users["owner"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_legacy_conversation_alias_reads_and_sends_to_the_canonical_history(chat_api):
    client, factory, users, conversation_id, _ = chat_api
    alias_id = str(uuid4())
    with factory() as db:
        db.add(ConversationAlias(alias_id=alias_id, canonical_id=conversation_id))
        db.commit()
    response = send(client, users, alias_id)
    assert response.status_code == 201
    assert response.json()["conversation_id"] == conversation_id
    response = client.get(messages_url(alias_id), headers=auth(users["owner"]))
    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id
    assert [item["seq"] for item in response.json()["items"]] == [1]
    assert client.get(messages_url(alias_id), headers=auth(users["stranger"])).status_code == 403


def test_jobs_auto_creation_and_direct_creation_share_the_same_unique_key(chat_api):
    from backend.app.api.v1.routes.jobs import _create_match_conversation

    _, factory, users, _, _ = chat_api
    source_id = str(uuid4())
    with factory() as db:
        automatic = _create_match_conversation(
            db,
            patient_id=users["owner"],
            caregiver_id=users["peer"],
            source_type="application",
            source_id=source_id,
        )
        manual, created = get_or_create_conversation(
            db,
            owner_id=users["peer"],
            participant_a=users["peer"],
            participant_b=users["owner"],
            source_type="application",
            source_id=source_id,
        )
        assert not created
        assert automatic.id == manual.id
        db.commit()
        assert (
            db.query(Conversation).filter_by(source_type="application", source_id=source_id).count()
            == 1
        )


def test_v1_and_v2_share_the_same_local_account_rate_budget(chat_api, monkeypatch):
    client, factory, users, conversation_id, _ = chat_api
    monkeypatch.setattr(settings, "care_chat_send_rate", 1)
    monkeypatch.setattr(settings, "care_chat_send_burst", 1)
    monkeypatch.setattr(care_chat_admission, "time", SimpleNamespace(monotonic=lambda: 1000.0))
    first = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth(users["owner"]),
        json={"sender_id": users["owner"], "body": "legacy send"},
    )
    assert first.status_code == 201
    blocked = send(client, users, conversation_id)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    with factory() as db:
        assert db.get(Conversation, conversation_id).last_seq == 1


def test_shared_redis_rate_budget_returns_retry_after_without_writing(chat_api, monkeypatch):
    client, factory, users, conversation_id, _ = chat_api
    monkeypatch.setattr(care_chat_admission._redis, "eval", lambda *args: 2)
    response = send(client, users, conversation_id)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"
    with factory() as db:
        assert db.get(Conversation, conversation_id).last_seq == 0


def test_redis_outage_keeps_local_rate_limit_and_recovers_after_refill(chat_api, monkeypatch):
    client, _, users, conversation_id, _ = chat_api
    monkeypatch.setattr(settings, "care_chat_send_rate", 1)
    monkeypatch.setattr(settings, "care_chat_send_burst", 1)
    clock = [1000.0]
    attempts = []

    def unavailable(*args):
        attempts.append(True)
        raise RedisConnectionError("simulated rate-limit Redis outage")

    monkeypatch.setattr(care_chat_admission, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(care_chat_admission._redis, "eval", unavailable)
    assert send(client, users, conversation_id).status_code == 201
    assert send(client, users, conversation_id).status_code == 429
    clock[0] += 2
    assert send(client, users, conversation_id).status_code == 201
    assert len(attempts) == 1, "Circuit breaker should suppress repeated unavailable Redis calls"


@pytest.mark.parametrize("method", ["get", "post"])
def test_saturated_worker_returns_503_with_retry_after(chat_api, monkeypatch, method):
    from backend.app.api.v2 import conversations as routes
    from backend.app.services import care_chat_pages

    client, factory, users, conversation_id, _ = chat_api
    if method == "get":
        monkeypatch.setattr(care_chat_pages, "read_slots", BoundedSemaphore(0))
        response = client.get(messages_url(conversation_id), headers=auth(users["owner"]))
    else:
        monkeypatch.setattr(routes, "send_slots", BoundedSemaphore(0))
        response = send(client, users, conversation_id)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    with factory() as db:
        assert db.get(Conversation, conversation_id).last_seq == 0


def test_failed_send_releases_worker_slot_for_the_next_request(chat_api, monkeypatch):
    from backend.app.api.v2 import conversations as routes

    client, _, users, conversation_id, _ = chat_api
    monkeypatch.setattr(routes, "send_slots", BoundedSemaphore(1))
    key = str(uuid4())
    assert send(client, users, conversation_id, client_message_id=key).status_code == 201
    assert (
        send(client, users, conversation_id, client_message_id=key, body="conflict").status_code
        == 409
    )
    assert send(client, users, conversation_id).status_code == 201
