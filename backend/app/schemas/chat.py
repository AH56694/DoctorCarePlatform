from pydantic import BaseModel, Field


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    user_id: str | None = None


class IntentResult(BaseModel):
    category: str
    subcategory: str = ""
    confidence: float


class AiChatResponse(BaseModel):
    answer: str
    intent: IntentResult
    cache_hit_level: str = "miss"
    citations: list[dict] = []
