import json
from unittest.mock import Mock

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from backend.app.core.config import settings
from backend.app.db.models import (
    AdminLog,
    AiMessage,
    AiSession,
    Base,
    CaregiverProfile,
    Conversation,
    PatientProfile,
    Review,
    User,
    UserRole,
)
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.schemas.chat import AiChatResponse, IntentResult
from backend.app.services.auth import decode_access_token, issue_access_token
from backend.app.services.message_cache import message_cache
from backend.app.services.rag_client import RagServiceClient
from backend.app.services.rate_limit import AuthRateLimiter


@pytest.fixture
def secured_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    app = create_app()

    def database():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(message_cache, "add_message", lambda *args: None)
    with factory() as db:
        users = {}
        for name, role in (("owner", "patient"), ("stranger", "patient"), ("admin", "admin")):
            user = User(phone=name, active_role=role, status="active")
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role=role, is_active=True))
            users[name] = user.id
        for name in ("owner", "stranger"):
            db.add(PatientProfile(user_id=users[name]))
        db.commit()
    with TestClient(app) as client:
        yield client, factory, users
    engine.dispose()


def headers(user_id):
    return {"Authorization": f"Bearer {issue_access_token(user_id)}"}


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/ai/sessions", None),
    ("get", "/api/v1/ai/sessions/unknown/messages", None),
    ("post", "/api/v1/ai/chat", {"message": "hello"}),
    ("post", "/api/v1/ai/chat/stream", {"message": "hello"}),
])
def test_ai_requires_authentication(secured_api, method, path, body):
    client, _, _ = secured_api
    response = client.request(method, path, json=body)
    assert response.status_code == 401


def test_ai_history_is_private_even_without_user_filter(secured_api):
    client, factory, users = secured_api
    with factory() as db:
        private = AiSession(user_id=users["owner"], title="private medical history")
        orphan = AiSession(user_id=None, title="unclaimed legacy history")
        db.add_all([private, orphan])
        db.flush()
        db.add(AiMessage(
            session_id=private.id, sender="user", content="sensitive",
            user_message="sensitive", intent_category="medical_consult",
        ))
        db.commit()
    assert client.get("/api/v1/ai/sessions", headers=headers(users["stranger"])).json() == []
    for actor in ("stranger", "admin"):
        response = client.get(
            f"/api/v1/ai/sessions/{private.id}/messages", headers=headers(users[actor]),
        )
        assert response.status_code == 403
    for session in (private, orphan):
        response = client.post("/api/v1/ai/chat", headers=headers(users["stranger"]), json={
            "message": "read history", "conversation_id": session.id,
        })
        assert response.status_code == 403
    response = client.get(
        f"/api/v1/ai/sessions?user_id={users['owner']}", headers=headers(users["stranger"]),
    )
    assert response.status_code == 403
    assert client.get(
        f"/api/v1/ai/sessions/{private.id}/messages", headers=headers(users["owner"]),
    ).json()[0]["content"] == "sensitive"


def test_gateway_derives_identity_and_admin_privileges(secured_api, monkeypatch):
    client, factory, users = secured_api
    captured = []

    async def answer(self, payload):
        captured.append(payload)
        return AiChatResponse(answer="answer", intent=IntentResult(category="chitchat", confidence=1))

    monkeypatch.setattr(RagServiceClient, "chat", answer)
    response = client.post("/api/v1/ai/chat", headers=headers(users["owner"]), json={
        "message": "hello", "is_admin": True,
    })
    assert response.status_code == 200
    assert captured[0].user_id == users["owner"]
    assert captured[0].is_admin is False
    with factory() as db:
        assert db.get(AiSession, response.json()["session_id"]).user_id == users["owner"]
        assert db.query(AiMessage).count() == 2
    response = client.post("/api/v1/ai/chat", headers=headers(users["owner"]), json={
        "message": "hello", "user_id": users["admin"],
    })
    assert response.status_code == 403
    assert len(captured) == 1
    response = client.post("/api/v1/ai/chat", headers=headers(users["admin"]), json={"message": "hi"})
    assert response.status_code == 200
    assert captured[-1].is_admin is True


@pytest.mark.parametrize("failed", [False, True])
def test_stream_persists_only_successful_response(secured_api, monkeypatch, failed):
    client, factory, users = secured_api

    async def events(self, payload):
        yield {"type": "token", "content": "answer"}
        if failed:
            yield {"type": "error", "content": "secret database password"}

    monkeypatch.setattr(RagServiceClient, "stream_chat_events", events)
    response = client.post(
        "/api/v1/ai/chat/stream", headers=headers(users["owner"]), json={"message": "hi"},
    )
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events[-1]["type"] == ("error" if failed else "final")
    assert "secret database password" not in response.text
    with factory() as db:
        assert db.query(AiMessage).count() == (0 if failed else 2)


def test_unknown_ai_session_and_oversized_message_rejected(secured_api):
    client, _, users = secured_api
    auth = headers(users["owner"])
    assert client.post("/api/v1/ai/chat", headers=auth, json={
        "message": "hello", "conversation_id": "unclaimed-client-id",
    }).status_code == 404
    response = client.post("/api/v1/ai/chat", headers=auth, json={"message": "private" * 2000})
    assert response.status_code == 422
    assert "privateprivate" not in response.text
    assert response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


def test_identity_requires_review_and_edits_invalidate_it(secured_api):
    client, factory, users = secured_api
    path = f"/api/v1/accounts/{users['owner']}/profiles/patient"
    data = {"real_name": "Test Patient", "id_number": "test-identity", "basic_info": {}}
    result = client.put(path, headers=headers(users["owner"]), json=data).json()
    assert result["patient_profile"]["id_verified"] is False
    assert result["patient_profile"]["verification_status"] == "pending"
    evidence = {"approved": True, "evidence_reference": "offline-evidence-001"}
    assert client.post(path + "/identity-review", headers=headers(users["owner"]), json=evidence).status_code == 403
    response = client.post(path + "/identity-review", headers=headers(users["admin"]), json=evidence)
    assert response.json()["patient_profile"]["id_verified"] is True
    data.pop("id_number")
    data["basic_info"] = {"care_need": "daily care"}
    assert client.put(path, headers=headers(users["owner"]), json=data).json()["patient_profile"]["id_verified"] is True
    data["real_name"] = "Changed Patient"
    result = client.put(path, headers=headers(users["owner"]), json=data).json()
    assert result["patient_profile"]["id_verified"] is False
    with factory() as db:
        audit = db.query(AdminLog).filter_by(action="identity.review").one()
        assert audit.admin_id == users["admin"]
        assert "test-identity" not in json.dumps(audit.detail)


def test_review_update_refreshes_average_and_filter_cannot_bypass_ownership(secured_api):
    client, factory, users = secured_api
    with factory() as db:
        profile = CaregiverProfile(user_id=users["stranger"], rating_avg=5)
        conversation = Conversation(
            kind="care_chat", owner_id=users["owner"],
            participant_a=users["owner"], participant_b=users["stranger"],
        )
        db.add_all([profile, conversation])
        db.flush()
        review = Review(
            conversation_id=conversation.id, reviewer_id=users["owner"],
            reviewee_id=users["stranger"], score=5,
        )
        db.add(review)
        db.commit()
    response = client.put(
        f"/api/v1/reviews/{review.id}?reviewer_id={users['owner']}",
        headers=headers(users["owner"]), json={"score": 2, "tags": [], "comment": "updated"},
    )
    assert response.status_code == 200
    with factory() as db:
        assert db.get(CaregiverProfile, profile.id).rating_avg == 2
    assert client.get(
        f"/api/v1/reviews?conversation_id={conversation.id}", headers=headers(users["admin"]),
    ).status_code == 403


def test_token_without_expiry_is_rejected():
    token = jwt.encode(
        {"sub": "owner", "iss": settings.auth_issuer, "type": "access"},
        settings.auth_secret_key, algorithm="HS256",
    )
    assert decode_access_token(token) is None


def test_auth_rate_limit_is_bounded_and_production_fails_closed(monkeypatch):
    limiter = AuthRateLimiter()
    limiter.client = Mock()
    limiter.client.eval.side_effect = RedisConnectionError("private Redis address")
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_rate_limit_attempts", 2)
    request = Request({"type": "http", "client": ("127.0.0.1", 123), "headers": []})
    limiter.check(request, "13800000000")
    limiter.check(request, "13800000000")
    with pytest.raises(HTTPException) as rejected:
        limiter.check(request, "13800000000")
    assert rejected.value.status_code == 429
    assert int(rejected.value.headers["Retry-After"]) > 0
    assert "13800000000" not in str(limiter._local)
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(HTTPException) as unavailable:
        limiter.check(request, "13800000000")
    assert unavailable.value.status_code == 503


def test_upstream_error_is_redacted(secured_api, monkeypatch):
    client, _, users = secured_api

    async def fail(self, payload):
        raise httpx.ConnectError("private-internal-host")

    monkeypatch.setattr(RagServiceClient, "chat", fail)
    response = client.post(
        "/api/v1/ai/chat", headers=headers(users["owner"]), json={"message": "hello"},
    )
    assert response.status_code == 502
    assert "private-internal-host" not in response.text
