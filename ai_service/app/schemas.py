from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    category: str
    subcategory: str = ""
    confidence: float = Field(ge=0, le=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    user_id: str | None = None


class Citation(BaseModel):
    title: str = ""
    source_url: str = ""
    snippet: str = ""


class ChatResponse(BaseModel):
    answer: str
    intent: IntentResult
    cache_hit_level: str = "miss"
    citations: list[Citation] = []


class EmbeddingRequest(BaseModel):
    texts: list[str]


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]
