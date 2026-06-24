from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]
