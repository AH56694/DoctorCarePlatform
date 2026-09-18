import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_agent_loop import QUESTION, make_agent


@pytest.fixture
def client(monkeypatch):
    from api import agent_routes

    agent = make_agent()
    monkeypatch.setattr(agent_routes, "orchestrator", agent)
    monkeypatch.setattr(agent_routes, "stored_states", {})
    app = FastAPI()
    app.include_router(agent_routes.router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client, agent


def test_sync_api_preserves_waiting_answer_and_run_status(client):
    http, agent = client
    response = http.post(
        "/api/agent/run", json={"input": "我头痛", "run_id": "wait", "conversation_id": "c"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "waiting"
    assert data["requires_input"]
    assert data["answer"]
    assert data["task_type"] == "knowledge_qa"
    state = http.get("/api/agent/run/wait").json()
    assert state["status"] == "waiting"
    assert state["stop_reason"] == "needs_user_input"


def test_stream_api_has_compatible_tokens_end_and_complete_frames(client):
    http, agent = client
    response = http.post("/api/agent/run/stream", json={"input": QUESTION, "run_id": "stream"})
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert events[-1] == {"type": "complete", "run_id": "stream"}
    assert any(event["type"] == "token" for event in events)
    end = next(event["content"] for event in events if event["type"] == "end")
    assert end["stop_reason"] == "answered"
    assert http.get("/api/agent/run/stream").json()["status"] == "completed"


def test_failed_run_is_not_reported_as_completed(client):
    http, agent = client

    def fail(state):
        raise RuntimeError("provider secret must not be exposed")

    agent.consultation.assess = fail
    response = http.post("/api/agent/run", json={"input": QUESTION})
    assert response.json()["status"] == "failed"
    assert response.json()["error"]
    assert "provider secret" not in response.text
