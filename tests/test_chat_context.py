import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from backend.app.api.v1.routes import chat as chat_routes
from backend.app.schemas.chat import AiChatRequest, AiChatResponse, IntentResult


def _response() -> AiChatResponse:
    return AiChatResponse(
        answer="回答",
        intent=IntentResult(category="medical_consult", confidence=0.9),
    )


def test_first_turn_uses_precreated_session_id_for_ai_memory(monkeypatch) -> None:
    captured = {}
    session = SimpleNamespace(id="generated-session")

    async def fake_chat(self, payload):
        captured["conversation_id"] = payload.conversation_id
        return _response()

    monkeypatch.setattr(chat_routes, "_prepare_ai_session", lambda db, payload: session)
    monkeypatch.setattr(chat_routes, "_persist_ai_messages", lambda *args, **kwargs: session)
    monkeypatch.setattr(chat_routes.RagServiceClient, "chat", fake_chat)

    current_user = SimpleNamespace(id="user-1", active_role="patient", roles=[])
    result = asyncio.run(
        chat_routes.chat(AiChatRequest(message="第一轮问题"), current_user=current_user, db=Mock())
    )

    assert captured["conversation_id"] == "generated-session"
    assert result.session_id == "generated-session"


def test_attachment_context_has_global_budget() -> None:
    payload = AiChatRequest(
        message="分析附件",
        attachments=[
            {"file_name": f"file-{index}.txt", "content": "x" * 12000}
            for index in range(8)
        ],
    )

    combined = chat_routes._message_with_attachments(payload)

    assert combined.count("x" * chat_routes.MAX_ATTACHMENT_ITEM_CHARS) == 3
    assert "file-3.txt" not in combined


def test_rejected_agent_evidence_clears_previously_streamed_sources():
    from backend.app.services.rag_client import RagServiceClient

    state = {"sources": [{"title": "候选资料"}], "answer_parts": []}
    events = chat_routes._normalize_stream_event(
        {"type": "sources", "content": []}, state, RagServiceClient(),
    )
    assert state["sources"] == []
    assert events == [{"type": "sources", "sources": []}]
    state["sources"] = [{"title": "旧的候选资料"}]
    chat_routes._normalize_stream_event(
        {"type": "end", "content": {"answer": "资料不足", "sources": []}}, state, RagServiceClient(),
    )
    assert state["sources"] == []
