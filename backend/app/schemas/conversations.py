from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    participant_a: str
    participant_b: str
    source_type: str = Field(default="", max_length=32)
    source_id: str | None = None
    title: str = Field(default="", max_length=160)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    participant_a: str | None = None
    participant_b: str | None = None
    kind: str = "care_chat"
    source_type: str = ""
    source_id: str | None = None
    title: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageCreate(BaseModel):
    sender_id: str
    body: str = Field(min_length=1, max_length=4000)
    attachment_url: str = Field(default="", max_length=500)
    attachment_type: str = Field(default="", max_length=64)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_id: str | None = None
    sender_type: str = "user"
    body: str
    content: str = ""
    attachment_url: str = ""
    attachment_type: str = ""
    created_at: datetime | None = None
