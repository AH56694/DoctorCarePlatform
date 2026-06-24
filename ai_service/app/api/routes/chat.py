from fastapi import APIRouter

from ai_service.app.schemas import ChatRequest, ChatResponse
from ai_service.app.services.chat_engine import ChatEngine

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    return await ChatEngine().answer(payload)
