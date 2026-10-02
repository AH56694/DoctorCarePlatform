"""Transactional care chat operations. Conversation locks define commit ordering."""

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.app.db.models import Conversation, ConversationAlias, Message


def conversation_key(participant_a: str, participant_b: str, source_type: str = "",
                     source_id: str | None = None) -> str:
    if source_type in {"", "profile"}:
        scope, scope_id = "direct", ""
    elif source_type in {"job", "application", "invitation"} and source_id:
        scope, scope_id = source_type, source_id
    else:
        raise HTTPException(400, "Unsupported or incomplete conversation source")
    identity = ["care_chat", *sorted([participant_a, participant_b]), scope, scope_id]
    return hashlib.sha256(json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def resolve_conversation(db: Session, conversation_id: str, *, for_update: bool = False) -> Conversation:
    query = db.query(Conversation).filter(Conversation.id == conversation_id)
    if for_update:
        query = query.populate_existing().with_for_update()
    conversation = query.first()
    if conversation is None:
        alias = db.get(ConversationAlias, conversation_id)
        if alias is not None:
            query = db.query(Conversation).filter(Conversation.id == alias.canonical_id)
            if for_update:
                query = query.populate_existing().with_for_update()
            conversation = query.first()
    if conversation is None or conversation.kind != "care_chat":
        raise HTTPException(404, "Conversation not found")
    return conversation


def require_participant(conversation: Conversation, user_id: str) -> None:
    if user_id not in {conversation.participant_a, conversation.participant_b}:
        raise HTTPException(403, "Only participants can access this conversation")


def get_or_create_conversation(db: Session, *, owner_id: str, participant_a: str,
                               participant_b: str, source_type: str = "",
                               source_id: str | None = None, title: str = "") -> tuple[Conversation, bool]:
    if not participant_a or not participant_b or participant_a == participant_b:
        raise HTTPException(400, "Two different participants are required")
    key = conversation_key(participant_a, participant_b, source_type, source_id)
    existing = db.query(Conversation).filter(Conversation.conversation_key == key).first()
    if existing:
        return existing, False
    conversation = Conversation(
        owner_id=owner_id, participant_a=participant_a, participant_b=participant_b,
        kind="care_chat", conversation_key=key, source_type=source_type, source_id=source_id,
        title=title, last_seq=0, last_message_at=datetime.now(UTC).replace(tzinfo=None),
    )
    try:
        # Roll back only this insertion, never the surrounding recruitment transaction.
        with db.begin_nested():
            db.add(conversation)
            db.flush()
    except IntegrityError:
        # A current read sees the winning insertion even under MySQL REPEATABLE READ.
        existing = (db.query(Conversation).filter(Conversation.conversation_key == key)
                    .populate_existing().with_for_update().first())
        if existing is None:
            raise
        return existing, False
    return conversation, True


def _send_message_once(db: Session, *, conversation_id: str, sender_id: str,
                       client_message_id: str | None, body: str,
                       attachment_url: str, attachment_type: str) -> tuple[Message, bool]:
    conversation = resolve_conversation(db, conversation_id, for_update=True)
    require_participant(conversation, sender_id)
    if client_message_id is not None:
        existing = (db.query(Message).filter(
            Message.conversation_id == conversation.id, Message.sender_id == sender_id,
            Message.client_message_id == client_message_id,
        ).with_for_update().first())
        if existing:
            if (existing.body, existing.attachment_url, existing.attachment_type) != (
                body, attachment_url, attachment_type,
            ):
                raise HTTPException(409, "client_message_id was already used for a different message")
            db.commit()
            return existing, False
    now = datetime.now(UTC).replace(tzinfo=None)
    seq = conversation.last_seq + 1
    message = Message(
        conversation_id=conversation.id, sender_id=sender_id, sender_type="user",
        client_message_id=client_message_id, seq=seq, body=body, content=body,
        attachment_url=attachment_url, attachment_type=attachment_type, created_at=now,
    )
    db.add(message)
    conversation.last_seq = seq
    conversation.last_message_at = max(conversation.last_message_at or now, now)
    db.flush()
    db.commit()
    return message, True


def send_message(db: Session, *, conversation_id: str, sender_id: str,
                 client_message_id: str | None, body: str,
                 attachment_url: str = "", attachment_type: str = "") -> tuple[Message, bool]:
    """Owns the send transaction; never perform cache or network work while locked."""
    for attempt in range(3):
        try:
            return _send_message_once(
                db, conversation_id=conversation_id, sender_id=sender_id,
                client_message_id=client_message_id, body=body,
                attachment_url=attachment_url, attachment_type=attachment_type,
            )
        except OperationalError as exc:
            db.rollback()
            code = getattr(exc.orig, "args", (None,))[0]
            if code not in {1205, 1213}:
                raise
            if attempt == 2:
                raise HTTPException(503, "Chat is busy; retry with the same message ID",
                                    headers={"Retry-After": "1"}) from exc
        except Exception:
            db.rollback()
            raise
    raise AssertionError("unreachable")
