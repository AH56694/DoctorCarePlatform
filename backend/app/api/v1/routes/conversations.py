from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.db.models import Conversation, Message, User
from backend.app.db.session import get_db
from backend.app.schemas.conversations import ConversationCreate, ConversationRead, MessageCreate, MessageRead

router = APIRouter()


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _is_participant(conversation: Conversation, user_id: str) -> bool:
    return user_id in {conversation.participant_a, conversation.participant_b}


def _default_title(db: Session, participant_a: str, participant_b: str) -> str:
    left = _get_user(db, participant_a)
    right = _get_user(db, participant_b)
    return f"{left.display_name or left.phone} / {right.display_name or right.phone}"


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)) -> Conversation:
    if payload.participant_a == payload.participant_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Participants cannot be the same")
    _get_user(db, payload.participant_a)
    _get_user(db, payload.participant_b)

    query = db.query(Conversation).filter(
        Conversation.kind == "care_chat",
        Conversation.participant_a.in_([payload.participant_a, payload.participant_b]),
        Conversation.participant_b.in_([payload.participant_a, payload.participant_b]),
    )
    if payload.source_type and payload.source_id:
        query = query.filter(Conversation.source_type == payload.source_type, Conversation.source_id == payload.source_id)
    existing = query.first()
    if existing:
        return existing

    conversation = Conversation(
        owner_id=payload.participant_a,
        participant_a=payload.participant_a,
        participant_b=payload.participant_b,
        kind="care_chat",
        source_type=payload.source_type,
        source_id=payload.source_id,
        title=payload.title or _default_title(db, payload.participant_a, payload.participant_b),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    _get_user(db, user_id)
    return (
        db.query(Conversation)
        .filter(or_(Conversation.participant_a == user_id, Conversation.participant_b == user_id))
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[Message]:
    conversation = _get_conversation(db, conversation_id)
    if not _is_participant(conversation, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only participants can read messages")
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(200)
        .all()
    )


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
) -> Message:
    conversation = _get_conversation(db, conversation_id)
    if not _is_participant(conversation, payload.sender_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only participants can send messages")
    message = Message(
        conversation_id=conversation_id,
        sender_id=payload.sender_id,
        sender_type="user",
        body=payload.body,
        content=payload.body,
        attachment_url=payload.attachment_url,
        attachment_type=payload.attachment_type,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
