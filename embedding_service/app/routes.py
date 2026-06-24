from fastapi import APIRouter

from embedding_service.app.config import settings
from embedding_service.app.encoder import encoder
from embedding_service.app.schemas import EmbeddingRequest, EmbeddingResponse

router = APIRouter()


@router.post("/embeddings", response_model=EmbeddingResponse)
async def embeddings(payload: EmbeddingRequest) -> EmbeddingResponse:
    vectors = encoder.encode(payload.texts)
    dimension = len(vectors[0]) if vectors else settings.embedding_dimension
    return EmbeddingResponse(
        model=settings.embedding_model,
        dimension=dimension,
        embeddings=vectors,
    )
