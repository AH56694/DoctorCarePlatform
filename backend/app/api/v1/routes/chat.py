from fastapi import APIRouter

from backend.app.schemas.chat import AiChatRequest, AiChatResponse
from backend.app.services.ai_client import AiServiceClient

router = APIRouter()


@router.post("/chat", response_model=AiChatResponse)
async def chat(payload: AiChatRequest) -> AiChatResponse:
    return await AiServiceClient().chat(payload)
