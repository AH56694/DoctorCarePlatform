import httpx

from backend.app.core.config import settings
from backend.app.schemas.chat import AiChatRequest, AiChatResponse


class AiServiceClient:
    def __init__(self, base_url: str = str(settings.ai_service_url)) -> None:
        self.base_url = base_url.rstrip("/")

    async def chat(self, payload: AiChatRequest) -> AiChatResponse:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/chat", json=payload.model_dump()
            )
            response.raise_for_status()
            return AiChatResponse.model_validate(response.json())
