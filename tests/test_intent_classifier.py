import asyncio

from ai_service.app.services.intent_classifier import IntentClassifier


def test_medication_intent() -> None:
    result = asyncio.run(IntentClassifier().classify("这个药每天吃几次，有什么副作用"))
    assert result.category == "medical_consult"
    assert result.subcategory == "medication_consult"


def test_emergency_intent() -> None:
    result = asyncio.run(IntentClassifier().classify("老人突然胸痛呼吸困难"))
    assert result.category == "emergency"
    assert result.confidence == 1
