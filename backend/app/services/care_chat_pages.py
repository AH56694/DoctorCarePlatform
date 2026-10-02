import base64
import hashlib
import hmac
import json
from datetime import datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import Conversation, Message
from backend.app.schemas.conversations import ConversationPage, ConversationRead, MessagePage, MessageRead
from backend.app.services.care_chat import require_participant, resolve_conversation
from backend.app.services.care_chat_admission import admitted, read_slots
from backend.app.services.care_chat_cache import latest_page_cache


def encode_cursor(kind: str, owner: str, value) -> str:
    raw = json.dumps([2, kind, owner, value], separators=(",", ":")).encode()
    signature = hmac.new(settings.auth_secret_key.encode(), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + signature).decode().rstrip("=")


def decode_cursor(cursor: str, kind: str, owner: str):
    try:
        if len(cursor) > 1024:
            raise ValueError()
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        payload, signature = raw[:-32], raw[-32:]
        expected = hmac.new(settings.auth_secret_key.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        version, purpose, subject, value = json.loads(payload)
        if (version, purpose, subject) != (2, kind, owner):
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(400, "Invalid or mismatched cursor") from exc


def message_page(db: Session, *, conversation_id: str, user_id: str, limit: int = 50,
                 before: str | None = None, after: str | None = None) -> MessagePage:
    if before and after:
        raise HTTPException(400, "before and after cannot be combined")
    conversation = resolve_conversation(db, conversation_id)
    require_participant(conversation, user_id)
    canonical_id, version = conversation.id, conversation.last_seq
    position = None
    if before or after:
        position = decode_cursor(before or after, "messages", canonical_id)
        if type(position) is not int or position < 0 or position > version:
            raise HTTPException(400, "Invalid message cursor position")
    # Authentication and the committed watermark come from the primary on EVERY
    # request, including hits. Release that read transaction before contacting Redis.
    db.commit()
    latest = not before and not after
    if latest:
        cached = latest_page_cache.get(canonical_id, version, limit)
        if cached is not None:
            try:
                page = MessagePage.model_validate(cached)
                expected_count = min(version, limit)
                if (page.conversation_id == canonical_id and len(page.items) == expected_count
                        and [item.seq for item in page.items] == list(range(version - expected_count + 1, version + 1))
                        and all(item.conversation_id == canonical_id for item in page.items)
                        and page.sync_cursor == encode_cursor("messages", canonical_id, version)
                        and page.has_more == (version > limit)
                        and page.older_cursor == (encode_cursor("messages", canonical_id, page.items[0].seq) if page.items and version > limit else None)):
                    return page
            except (ValidationError, ValueError, TypeError):
                pass
    with admitted(read_slots):
        query = db.query(Message).filter(Message.conversation_id == canonical_id, Message.seq <= version)
        if before:
            query = query.filter(Message.seq < position)
        elif after:
            query = query.filter(Message.seq > position)
        ascending = bool(after)
        rows = query.order_by(Message.seq.asc() if ascending else Message.seq.desc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        if not ascending:
            rows.reverse()
        items = [MessageRead.model_validate(row) for row in rows]
        # ACKs and the conversation watermark must not skip an unread backlog.
        sync = items[-1].seq if items else (position if after else version)
        page = MessagePage(
            conversation_id=canonical_id, items=items, has_more=has_more,
            older_cursor=(encode_cursor("messages", canonical_id, items[0].seq)
                          if items and (has_more if not after else items[0].seq > 1) else None),
            sync_cursor=encode_cursor("messages", canonical_id, sync),
        )
        db.commit()
    if latest:
        latest_page_cache.set(canonical_id, version, limit, page.model_dump(mode="json"))
    return page


def conversation_page(db: Session, *, user_id: str, limit: int = 20,
                      cursor: str | None = None) -> ConversationPage:
    boundary = None
    if cursor:
        value = decode_cursor(cursor, "conversations", user_id)
        try:
            stamp, identifier = value
            if not isinstance(identifier, str) or not identifier:
                raise ValueError()
            boundary = (datetime.fromisoformat(stamp) if stamp else None, identifier)
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, "Invalid conversation cursor position") from exc
    rows = {}
    with admitted(read_slots):
        # Two bounded index scans avoid an OR + full sort across a user's history.
        for participant in (Conversation.participant_a, Conversation.participant_b):
            query = db.query(Conversation).filter(participant == user_id, Conversation.kind == "care_chat")
            if boundary:
                stamp, identifier = boundary
                if stamp is None:
                    query = query.filter(Conversation.last_message_at.is_(None), Conversation.id < identifier)
                else:
                    query = query.filter(or_(
                        Conversation.last_message_at < stamp, Conversation.last_message_at.is_(None),
                        and_(Conversation.last_message_at == stamp, Conversation.id < identifier),
                    ))
            for row in query.order_by(Conversation.last_message_at.desc(), Conversation.id.desc()).limit(limit + 1):
                rows[row.id] = row
        ordered = sorted(rows.values(), key=lambda row: (row.last_message_at or datetime.min, row.id), reverse=True)
        has_more = len(ordered) > limit
        items = [ConversationRead.model_validate(row) for row in ordered[:limit]]
        next_cursor = None
        if items and has_more:
            last = items[-1]
            next_cursor = encode_cursor("conversations", user_id, [
                last.last_message_at.isoformat() if last.last_message_at else None, last.id,
            ])
        db.commit()
    return ConversationPage(items=items, next_cursor=next_cursor, has_more=has_more)
