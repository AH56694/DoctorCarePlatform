import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.db.models import AiMessage, AiSession
from backend.app.db.session import get_db
from backend.app.schemas.chat import AiChatRequest, AiChatResponse
from backend.app.services.rag_client import RagServiceClient

router = APIRouter()


@router.post("/chat", response_model=AiChatResponse)
async def chat(payload: AiChatRequest, db: Session = Depends(get_db)) -> AiChatResponse:
    ai_payload = payload.model_copy(update={"message": _message_with_attachments(payload)})
    response = await RagServiceClient().chat(ai_payload)
    session = _get_or_create_ai_session(db, payload, response)
    user_message = AiMessage(
        session_id=session.id,
        conversation_id=payload.conversation_id,
        sender="user",
        content=payload.message,
        user_message=payload.message,
        assistant_message="",
        intent_category=response.intent.category,
        intent_subcategory=response.intent.subcategory,
        intent_confidence=response.intent.confidence,
        cache_hit_level=response.cache_hit_level,
        metadata_json={"attachments": _attachment_metadata(payload)},
    )
    assistant_message = AiMessage(
        session_id=session.id,
        conversation_id=payload.conversation_id,
        sender="ai",
        content=response.answer,
        user_message=payload.message,
        assistant_message=response.answer,
        intent_category=response.intent.category,
        intent_subcategory=response.intent.subcategory,
        intent_confidence=response.intent.confidence,
        cache_hit_level=response.cache_hit_level,
        metadata_json={
            "citations": [_citation_to_dict(citation) for citation in response.citations],
            "source_attachments": _attachment_metadata(payload),
            "task_type": response.task_type,
            "run_id": response.run_id,
            "trace_id": response.trace_id,
            "steps": response.steps,
            "tool_calls": response.tool_calls,
            "intermediate_conclusions": response.intermediate_conclusions,
        },
    )
    if response.intent.category == "emergency":
        session.risk_flag = "emergency"
    db.add_all([user_message, assistant_message])
    db.commit()
    return response


@router.post("/chat/stream")
async def chat_stream(payload: AiChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    async def event_stream():
        client = RagServiceClient()
        ai_payload = payload.model_copy(update={"message": _message_with_attachments(payload)})
        stream_state: dict[str, Any] = {
            "answer_parts": [],
            "sources": [],
            "task_type": "knowledge_qa",
            "run_id": None,
            "trace_id": None,
            "steps": [],
            "tool_calls": [],
            "intermediate_conclusions": [],
        }

        yield _sse({"type": "status", "label": "正在理解问诊内容", "detail": "识别症状、附件和上下文"})

        try:
            async for event in client.stream_chat_events(ai_payload):
                for normalized in _normalize_stream_event(event, stream_state, client):
                    yield _sse(normalized)

            run_id = stream_state.get("run_id")
            if run_id:
                await _hydrate_final_run_state(client, str(run_id), stream_state)

            response = _response_from_stream_state(client, stream_state)
            _persist_ai_messages(db, payload, response)
            yield _sse({"type": "final", "response": response.model_dump()})
        except Exception as exc:
            yield _sse({"type": "error", "message": f"问诊流式响应失败：{exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _message_with_attachments(payload: AiChatRequest) -> str:
    if not payload.attachments:
        return payload.message

    attachment_sections = []
    for attachment in payload.attachments:
        content = attachment.content.strip()
        if not content:
            continue
        attachment_sections.append(
            f"File: {attachment.file_name or 'unnamed'}\n"
            f"Type: {attachment.file_type or 'unknown'}\n"
            f"Content excerpt:\n{content[:4000]}"
        )
    if not attachment_sections:
        return payload.message
    return f"{payload.message}\n\nUploaded consultation files:\n\n" + "\n\n---\n\n".join(attachment_sections)


def _normalize_stream_event(
    event: dict[str, Any],
    state: dict[str, Any],
    client: RagServiceClient,
) -> list[dict[str, Any]]:
    event_type = str(event.get("type") or "")
    output: list[dict[str, Any]] = []

    if event_type == "routed":
        task_type = str(event.get("task_type") or state["task_type"])
        state["task_type"] = task_type
        output.append(
            {
                "type": "status",
                "label": "已选择问诊处理链路",
                "detail": _task_type_label(task_type),
            }
        )
    elif event_type == "step_started":
        step = {
            "step_name": event.get("step_name") or "unknown",
            "step_type": event.get("step_type") or "",
            "status": "running",
        }
        state["steps"].append(step)
        output.append({"type": "status", "label": _step_label(step["step_name"]), "detail": "处理中"})
    elif event_type == "step_completed":
        step_name = str(event.get("step_name") or "unknown")
        step = {
            "step_name": step_name,
            "status": "completed",
            "output_data": event.get("output") if isinstance(event.get("output"), dict) else {},
        }
        state["steps"].append(step)
        output.append({"type": "status", "label": _step_label(step_name), "detail": "已完成"})
        step_output = step["output_data"]
        if isinstance(step_output, dict):
            sources = client._normalize_sources(step_output.get("sources") or [])
            if sources:
                state["sources"] = sources
                output.append({"type": "sources", "sources": sources})
            if step_name in {"knowledge_search", "question_rewrite", "rerank", "memory_read"}:
                tool_event = {
                    "tool_name": step_name,
                    "status": "completed",
                    "output": step_output,
                }
                state["tool_calls"].append(tool_event)
                output.append({"type": "tool", "tool_call": tool_event})
    elif event_type == "token":
        token = str(event.get("content") or "")
        if token:
            state["answer_parts"].append(token)
            output.append({"type": "token", "content": token})
    elif event_type == "answer":
        content = str(event.get("content") or "")
        if content:
            state["answer_parts"].append(content)
            output.append({"type": "token", "content": content})
        sources = client._normalize_sources(event.get("sources") or [])
        if sources:
            state["sources"] = sources
            output.append({"type": "sources", "sources": sources})
    elif event_type == "sources":
        sources = client._normalize_sources(event.get("content") or [])
        if sources:
            state["sources"] = sources
            output.append({"type": "sources", "sources": sources})
    elif event_type == "end":
        content = event.get("content")
        if isinstance(content, dict):
            answer = str(content.get("answer") or "")
            if answer and not "".join(state["answer_parts"]).strip():
                state["answer_parts"].append(answer)
                output.append({"type": "token", "content": answer})
            sources = client._normalize_sources(content.get("sources") or [])
            if sources:
                state["sources"] = sources
                output.append({"type": "sources", "sources": sources})
        elif isinstance(content, str) and content and not "".join(state["answer_parts"]).strip():
            state["answer_parts"].append(content)
            output.append({"type": "token", "content": content})
    elif event_type == "complete":
        state["run_id"] = event.get("run_id") or state.get("run_id")
        output.append({"type": "status", "label": "正在整理问诊结论", "detail": "汇总回答、来源和工具调用"})
    elif event_type == "error":
        output.append({"type": "error", "message": str(event.get("content") or "问诊处理失败")})

    return output


async def _hydrate_final_run_state(
    client: RagServiceClient,
    run_id: str,
    state: dict[str, Any],
) -> None:
    state["run_id"] = run_id
    try:
        run_status = await client.get_run_status(run_id)
    except Exception:
        run_status = {}
    if isinstance(run_status, dict):
        state["trace_id"] = run_status.get("trace_id") or state.get("trace_id")
        if isinstance(run_status.get("steps"), list):
            state["steps"] = [item for item in run_status["steps"] if isinstance(item, dict)]
        if isinstance(run_status.get("intermediate_conclusions"), list):
            state["intermediate_conclusions"] = [
                item for item in run_status["intermediate_conclusions"] if isinstance(item, dict)
            ]
    try:
        tool_calls = await client.get_run_tool_calls(run_id)
    except Exception:
        tool_calls = []
    if tool_calls:
        state["tool_calls"] = tool_calls


def _response_from_stream_state(
    client: RagServiceClient,
    state: dict[str, Any],
) -> AiChatResponse:
    task_type = str(state.get("task_type") or "knowledge_qa")
    answer = "".join(str(part) for part in state.get("answer_parts") or []).strip()
    if not answer:
        answer = "抱歉，本次问诊没有生成有效回复，请稍后重试或补充更具体的信息。"
    return AiChatResponse(
        answer=answer,
        intent=client._intent_from_task_type(task_type),
        cache_hit_level="agent-service",
        citations=client._normalize_sources(state.get("sources") or []),
        task_type=task_type,
        run_id=client._optional_str(state.get("run_id")),
        trace_id=client._optional_str(state.get("trace_id")),
        steps=[item for item in state.get("steps") or [] if isinstance(item, dict)],
        tool_calls=[item for item in state.get("tool_calls") or [] if isinstance(item, dict)],
        intermediate_conclusions=[
            item for item in state.get("intermediate_conclusions") or [] if isinstance(item, dict)
        ],
    )


def _persist_ai_messages(db: Session, payload: AiChatRequest, response: AiChatResponse) -> None:
    session = _get_or_create_ai_session(db, payload, response)
    user_message = AiMessage(
        session_id=session.id,
        conversation_id=payload.conversation_id,
        sender="user",
        content=payload.message,
        user_message=payload.message,
        assistant_message="",
        intent_category=response.intent.category,
        intent_subcategory=response.intent.subcategory,
        intent_confidence=response.intent.confidence,
        cache_hit_level=response.cache_hit_level,
        metadata_json={"attachments": _attachment_metadata(payload), "streamed": True},
    )
    assistant_message = AiMessage(
        session_id=session.id,
        conversation_id=payload.conversation_id,
        sender="ai",
        content=response.answer,
        user_message=payload.message,
        assistant_message=response.answer,
        intent_category=response.intent.category,
        intent_subcategory=response.intent.subcategory,
        intent_confidence=response.intent.confidence,
        cache_hit_level=response.cache_hit_level,
        metadata_json={
            "citations": [_citation_to_dict(citation) for citation in response.citations],
            "source_attachments": _attachment_metadata(payload),
            "task_type": response.task_type,
            "run_id": response.run_id,
            "trace_id": response.trace_id,
            "steps": response.steps,
            "tool_calls": response.tool_calls,
            "intermediate_conclusions": response.intermediate_conclusions,
            "streamed": True,
        },
    )
    if response.intent.category == "emergency":
        session.risk_flag = "emergency"
    db.add_all([user_message, assistant_message])
    db.commit()


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _task_type_label(task_type: str) -> str:
    labels = {
        "knowledge_qa": "医学知识检索问答",
        "reasoning": "多步骤医学推理",
        "chitchat": "基础问答",
        "knowledge_inspection": "知识库巡检",
        "admin_copilot": "管理助手",
    }
    return labels.get(task_type, task_type or "问诊处理")


def _step_label(step_name: str) -> str:
    labels = {
        "intent_recognition": "识别问诊意图",
        "question_classification": "判断问题类型",
        "clarification": "判断是否需要补充信息",
        "question_rewrite": "改写检索问题",
        "knowledge_search": "检索知识库文件",
        "result_evaluation": "评估检索结果",
        "rerank": "重排候选依据",
        "answer_generation": "生成问诊回复",
        "memory_read": "读取对话记忆",
        "memory_write": "写入对话记忆",
    }
    return labels.get(step_name, step_name.replace("_", " ") if step_name else "处理步骤")


def _attachment_metadata(payload: AiChatRequest) -> list[dict]:
    return [
        {
            "file_name": item.file_name,
            "file_type": item.file_type,
            "content_length": len(item.content or ""),
        }
        for item in payload.attachments
    ]


def _get_or_create_ai_session(db: Session, payload: AiChatRequest, response: AiChatResponse) -> AiSession:
    session = None
    if payload.conversation_id:
        session = db.query(AiSession).filter(AiSession.id == payload.conversation_id).first()
    if session is None:
        session_data = {
            "user_id": payload.user_id,
            "role_context": "patient",
            "title": payload.message[:80],
            "risk_flag": "emergency" if response.intent.category == "emergency" else "none",
            "metadata_json": {"source": "api.v1.ai.chat"},
        }
        if payload.conversation_id:
            session_data["id"] = payload.conversation_id
        session = AiSession(**session_data)
        db.add(session)
        db.flush()
    return session


def _citation_to_dict(citation: object) -> dict:
    if isinstance(citation, dict):
        return citation
    model_dump = getattr(citation, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return {"value": str(citation)}
