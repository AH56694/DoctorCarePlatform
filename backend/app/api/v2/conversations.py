from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.conversations import ConversationPage, MessageCreateV2, MessagePage, MessageRead
from backend.app.services.care_chat import send_message
from backend.app.services.care_chat_admission import admitted, check_send_rate, send_slots
from backend.app.services.care_chat_pages import conversation_page, message_page

router = APIRouter(prefix="/conversations", tags=["care-chat-v2"])


@router.get("", response_model=ConversationPage)
def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100), cursor: str | None = Query(None, max_length=1024),
    db: Session = Depends(get_db),
) -> ConversationPage:
    return conversation_page(db, user_id=current_user.id, limit=limit, cursor=cursor)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
def list_messages(
    conversation_id: str, current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=100),
    before: str | None = Query(None, max_length=1024), after: str | None = Query(None, max_length=1024),
    db: Session = Depends(get_db),
) -> MessagePage:
    return message_page(db, conversation_id=conversation_id, user_id=current_user.id,
                        limit=limit, before=before, after=after)


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=201)
def create_message(
    conversation_id: str, payload: MessageCreateV2, response: Response,
    current_user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db),
) -> MessageRead:
    user_id = current_user.id
    db.commit()
    check_send_rate(user_id)
    with admitted(send_slots):
        message, created = send_message(
            db, conversation_id=conversation_id, sender_id=user_id,
            client_message_id=str(payload.client_message_id), body=payload.body,
            attachment_url=payload.attachment_url, attachment_type=payload.attachment_type,
        )
        response.status_code = 201 if created else 200
        return MessageRead.model_validate(message)
