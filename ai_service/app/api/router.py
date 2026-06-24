from fastapi import APIRouter

from ai_service.app.api.routes import chat, intents

api_router = APIRouter()
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(intents.router, prefix="/intents", tags=["intents"])
