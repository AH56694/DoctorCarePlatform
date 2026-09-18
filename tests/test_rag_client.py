import asyncio
from typing import Any

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.schemas.chat import AiChatRequest
from backend.app.services.rag_client import RagServiceClient


def test_rag_task_type_maps_to_medical_consult() -> None:
    intent = RagServiceClient()._intent_from_task_type("knowledge_qa")
    assert intent.category == "medical_consult"
    assert intent.subcategory == "rag_knowledge_qa"


def test_failed_agent_run_is_not_presented_as_successful_answer(monkeypatch):
    async def failed(self, payload):
        return {"answer": "失败", "status": "failed", "error": True}

    monkeypatch.setattr(RagServiceClient, "_run_agent", failed)
    with pytest.raises(httpx.RequestError):
        asyncio.run(RagServiceClient().chat(AiChatRequest(message="问题")))


def test_rag_sources_are_normalized() -> None:
    sources = RagServiceClient()._normalize_sources([{"doc": "术后护理指南", "content": "观察伤口渗出。"}])
    assert sources == [
        {
            "title": "术后护理指南",
            "snippet": "观察伤口渗出。",
            "source_url": "",
            "doc": "术后护理指南",
            "content": "观察伤口渗出。",
        }
    ]


def test_agent_response_maps_trace_and_tool_calls(monkeypatch) -> None:
    async def fake_post(
        self: RagServiceClient,
        path: str,
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        assert path == "/api/agent/run"
        assert timeout == 90
        assert payload["input"] == "查看知识库巡检结果"
        assert payload["is_admin"] is True
        assert payload["user_id"] == "admin-1"
        return {
            "answer": "已完成巡检。",
            "task_type": "knowledge_inspection",
            "run_id": "run-1",
            "trace_id": "trace-1",
            "sources": [{"title": "巡检报告", "content": "无重复片段"}],
            "steps": [{"step_name": "admin_operation"}],
            "tool_calls": [{"tool_name": "knowledge_search", "status": "success"}],
            "intermediate_conclusions": [{"content": "知识库质量正常"}],
        }

    monkeypatch.setattr(RagServiceClient, "_post", fake_post)

    response = asyncio.run(
        RagServiceClient().chat(
            AiChatRequest(message="查看知识库巡检结果", user_id="admin-1", is_admin=True)
        )
    )

    assert response.intent.category == "platform_faq"
    assert response.intent.subcategory == "knowledge_inspection"
    assert response.cache_hit_level == "agent-service"
    assert response.run_id == "run-1"
    assert response.trace_id == "trace-1"
    assert response.tool_calls == [{"tool_name": "knowledge_search", "status": "success"}]


def test_agent_payload_forwards_explicit_context() -> None:
    payload = RagServiceClient()._agent_payload(
        AiChatRequest(
            message="它需要继续观察吗？",
            conversation_id="session-1",
            context="患者上一轮描述了术后疼痛。",
        )
    )

    assert payload["conversation_id"] == "session-1"
    assert payload["context"] == "患者上一轮描述了术后疼痛。"


def test_every_internal_request_sends_service_authentication(monkeypatch):
    requests = []
    original_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "rag_service_token", "test-internal-token")

    def respond(request):
        requests.append(request)
        assert request.headers["X-Service-Token"] == "test-internal-token"
        if request.url.path.endswith("/stream"):
            return httpx.Response(200, text='data: {"type":"token","content":"ok"}\n\n')
        return httpx.Response(200, json={"tool_calls": []})

    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )

    async def exercise():
        client = RagServiceClient("http://internal.test")
        await client._post("/api/agent/run", {}, 30)
        await client.get_run_status("run-1")
        await client.get_run_tool_calls("run-1")
        await client.ingest_knowledge({})
        await client.delete_knowledge(1)
        events = [item async for item in client.stream_chat_events(AiChatRequest(message="hello"))]
        assert events == [{"type": "token", "content": "ok"}]

    asyncio.run(exercise())
    assert len(requests) == 6


def test_stream_has_total_deadline_even_if_upstream_keeps_sending(monkeypatch):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "rag_stream_timeout_seconds", 0.05)

    class EndlessStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(0.005)
                yield b'data: {"type":"token","content":"x"}\n\n'

    def respond(request):
        return httpx.Response(200, stream=EndlessStream())

    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )

    async def consume():
        async for _ in RagServiceClient().stream_chat_events(AiChatRequest(message="hello")):
            pass

    with pytest.raises(TimeoutError):
        asyncio.run(consume())
