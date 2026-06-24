from fastapi import APIRouter

from ai_service.app.schemas import ChatRequest, IntentResult
from ai_service.app.services.intent_classifier import IntentClassifier

router = APIRouter()


@router.post("/classify", response_model=IntentResult)
async def classify(payload: ChatRequest) -> IntentResult:
    return await IntentClassifier().classify(payload.message)
