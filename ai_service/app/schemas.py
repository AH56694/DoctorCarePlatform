from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    category: str
    subcategory: str = ""
    confidence: float = Field(ge=0, le=1)


class ChatAttachment(BaseModel):
    file_name: str = Field(default="", max_length=255)
    file_type: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=12000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    user_id: str | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


class Citation(BaseModel):
    title: str = ""
    source_url: str = ""
    snippet: str = ""


class ChatResponse(BaseModel):
    answer: str
    intent: IntentResult
    cache_hit_level: str = "miss"
    citations: list[Citation] = Field(default_factory=list)


class EmbeddingRequest(BaseModel):
    texts: list[str]


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]
