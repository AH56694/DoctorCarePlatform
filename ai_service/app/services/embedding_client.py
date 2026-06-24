import httpx

from ai_service.app.core.config import settings
from ai_service.app.schemas import EmbeddingResponse


class EmbeddingClient:
    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.embedding_service_url.rstrip('/')}/api/v1/embeddings",
                json={"texts": texts},
            )
            response.raise_for_status()
            return EmbeddingResponse.model_validate(response.json())
