from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AiAttachment(BaseModel):
    file_name: str = Field(default="", max_length=255)
    file_type: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=12000)


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    user_id: str | None = None
    context: str = Field(default="", max_length=24000)
    is_admin: bool = False
    attachments: list[AiAttachment] = Field(default_factory=list, max_length=8)


class IntentResult(BaseModel):
    category: str
    subcategory: str = ""
    confidence: float


class AiChatResponse(BaseModel):
    answer: str
    intent: IntentResult
    cache_hit_level: str = "miss"
    citations: list[dict] = Field(default_factory=list)
    task_type: str = "knowledge_qa"
    run_id: str | None = None
    trace_id: str | None = None
    session_id: str | None = None
    steps: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    intermediate_conclusions: list[dict] = Field(default_factory=list)


class AiSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    role_context: str = "patient"
    title: str = ""
    risk_flag: str = "none"
    summary: str = ""
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AiMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str | None = None
    conversation_id: str | None = None
    sender: str
    content: str = ""
    user_message: str = ""
    assistant_message: str = ""
    intent_category: str = ""
    intent_subcategory: str = ""
    intent_confidence: float = 0
    cache_hit_level: str = "miss"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
