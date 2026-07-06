import asyncio
from typing import Any

from backend.app.schemas.chat import AiChatRequest
from backend.app.services.rag_client import RagServiceClient


def test_rag_task_type_maps_to_medical_consult() -> None:
    intent = RagServiceClient()._intent_from_task_type("knowledge_qa")
    assert intent.category == "medical_consult"
    assert intent.subcategory == "rag_knowledge_qa"


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
