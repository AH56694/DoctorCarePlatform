from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.schemas.chat import AiChatRequest, AiChatResponse, IntentResult


class RagServiceClient:
    def __init__(self, base_url: str = str(settings.rag_service_url)) -> None:
        self.base_url = base_url.rstrip("/")

    async def chat(self, payload: AiChatRequest) -> AiChatResponse:
        request_payload = {
            "question": payload.message,
            "context": "",
            "is_admin": False,
        }
        if payload.conversation_id:
            request_payload["conversation_id"] = payload.conversation_id
        if payload.user_id:
            request_payload["username"] = payload.user_id
        data = await self._post("/api/ask", request_payload, timeout=60)
        task_type = str(data.get("task_type") or "knowledge_qa")
        return AiChatResponse(
            answer=str(data.get("answer") or ""),
            intent=self._intent_from_task_type(task_type),
            cache_hit_level=str(data.get("cache_hit_level") or "rag-service"),
            citations=self._normalize_sources(data.get("sources") or []),
        )

    async def ingest_knowledge(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/v1/knowledge/ingest", payload, timeout=120)

    async def delete_knowledge(self, doc_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.delete(f"{self.base_url}/api/v1/knowledge/{doc_id}")
            response.raise_for_status()
            return response.json()

    async def _post(self, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()

    def _intent_from_task_type(self, task_type: str) -> IntentResult:
        if task_type == "chitchat":
            return IntentResult(category="chitchat", subcategory="", confidence=0.86)
        if task_type == "admin_copilot":
            return IntentResult(category="platform_faq", subcategory="admin_copilot", confidence=0.82)
        return IntentResult(category="medical_consult", subcategory="rag_knowledge_qa", confidence=0.9)

    def _normalize_sources(self, sources: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for source in sources:
            if isinstance(source, dict):
                normalized.append(
                    {
                        "title": source.get("title") or source.get("doc") or source.get("source") or "知识库片段",
                        "snippet": source.get("snippet") or source.get("content") or "",
                        "source_url": source.get("source_url") or source.get("url") or "",
                        **source,
                    }
                )
            else:
                normalized.append({"title": "知识库片段", "snippet": str(source)})
        return normalized
