import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.schemas.chat import AiChatRequest, AiChatResponse, IntentResult


class RagServiceClient:
    def __init__(self, base_url: str = str(settings.rag_service_url)) -> None:
        self.base_url = base_url.rstrip("/")

    async def chat(self, payload: AiChatRequest) -> AiChatResponse:
        data = await self._run_agent(payload)
        task_type = str(data.get("task_type") or "knowledge_qa")
        return AiChatResponse(
            answer=str(data.get("answer") or ""),
            intent=self._intent_from_task_type(task_type),
            cache_hit_level=str(data.get("cache_hit_level") or "agent-service"),
            citations=self._normalize_sources(data.get("sources") or []),
            task_type=task_type,
            run_id=self._optional_str(data.get("run_id")),
            trace_id=self._optional_str(data.get("trace_id")),
            steps=self._normalize_dict_list(data.get("steps")),
            tool_calls=self._normalize_dict_list(data.get("tool_calls")),
            intermediate_conclusions=self._normalize_dict_list(data.get("intermediate_conclusions")),
        )

    async def stream_chat_events(self, payload: AiChatRequest) -> AsyncIterator[dict[str, Any]]:
        agent_payload = self._agent_payload(payload)
        async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/agent/run/stream",
                json=agent_payload,
            ) as response:
                response.raise_for_status()
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        raw_event, buffer = buffer.split("\n\n", 1)
                        parsed = self._parse_sse_event(raw_event)
                        if parsed is not None:
                            yield parsed
                parsed = self._parse_sse_event(buffer)
                if parsed is not None:
                    yield parsed

    async def get_run_status(self, run_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get(f"{self.base_url}/api/agent/run/{run_id}")
            response.raise_for_status()
            return response.json()

    async def get_run_tool_calls(self, run_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get(f"{self.base_url}/api/agent/run/{run_id}/tool-calls")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
        return self._normalize_dict_list(data.get("tool_calls"))

    async def _run_agent(self, payload: AiChatRequest) -> dict[str, Any]:
        request_payload = self._agent_payload(payload)

        try:
            return await self._post("/api/agent/run", request_payload, timeout=90)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return await self._legacy_ask(payload)
            raise
        except httpx.RequestError:
            raise

    async def _legacy_ask(self, payload: AiChatRequest) -> dict[str, Any]:
        request_payload: dict[str, Any] = {
            "question": payload.message,
            "context": payload.context,
            "is_admin": payload.is_admin,
        }
        if payload.conversation_id:
            request_payload["conversation_id"] = payload.conversation_id
        if payload.user_id:
            request_payload["username"] = payload.user_id
        data = await self._post("/api/ask", request_payload, timeout=60)
        data.setdefault("cache_hit_level", "rag-service")
        return data

    def _agent_payload(self, payload: AiChatRequest) -> dict[str, Any]:
        request_payload: dict[str, Any] = {
            "input": payload.message,
            "context": payload.context,
            "is_admin": payload.is_admin,
        }
        if payload.conversation_id:
            request_payload["conversation_id"] = payload.conversation_id
        if payload.user_id:
            request_payload["user_id"] = payload.user_id
        return request_payload

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
        if task_type == "knowledge_inspection":
            return IntentResult(category="platform_faq", subcategory="knowledge_inspection", confidence=0.82)
        if task_type == "reasoning":
            return IntentResult(category="medical_consult", subcategory="reasoning", confidence=0.86)
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

    def _normalize_dict_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def _parse_sse_event(self, raw_event: str) -> dict[str, Any] | None:
        data_lines = []
        for line in raw_event.splitlines():
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        if not data_lines:
            return None
        data = "\n".join(data_lines).strip()
        if not data:
            return None
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return {"type": "raw", "content": data}
        return parsed if isinstance(parsed, dict) else {"type": "raw", "content": parsed}
