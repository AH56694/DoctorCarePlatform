from pydantic import BaseModel, Field


class AiAttachment(BaseModel):
    file_name: str = Field(default="", max_length=255)
    file_type: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=12000)


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    user_id: str | None = None
    attachments: list[AiAttachment] = Field(default_factory=list)


class IntentResult(BaseModel):
    category: str
    subcategory: str = ""
    confidence: float


class AiChatResponse(BaseModel):
    answer: str
    intent: IntentResult
    cache_hit_level: str = "miss"
    citations: list[dict] = Field(default_factory=list)
