from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.models import AiMessage, AiSession
from backend.app.db.session import get_db
from backend.app.schemas.chat import AiChatRequest, AiChatResponse
from backend.app.services.ai_client import AiServiceClient

router = APIRouter()


@router.post("/chat", response_model=AiChatResponse)
async def chat(payload: AiChatRequest, db: Session = Depends(get_db)) -> AiChatResponse:
    ai_payload = payload.model_copy(update={"message": _message_with_attachments(payload)})
    response = await AiServiceClient().chat(ai_payload)
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
        },
    )
    if response.intent.category == "emergency":
        session.risk_flag = "emergency"
    db.add_all([user_message, assistant_message])
    db.commit()
    return response


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
