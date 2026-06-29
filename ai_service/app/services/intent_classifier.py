import json
import re

import httpx

from ai_service.app.core.config import settings
from ai_service.app.domain.intents import (
    CHITCHAT_KEYWORDS,
    EMERGENCY_KEYWORDS,
    MEDICAL_SUBCATEGORIES,
    PLATFORM_SUBCATEGORIES,
    RULES,
    TOP_LEVEL_CATEGORIES,
)
from ai_service.app.schemas import IntentResult
from ai_service.app.services.cache import cache_hash, l1_cache


class IntentClassifier:
    async def classify(self, message: str) -> IntentResult:
        emergency = self.emergency_filter(message)
        if emergency:
            return emergency

        cache_key = f"intent:{cache_hash(message)}"
        cached = l1_cache.get(cache_key)
        if cached:
            try:
                return IntentResult.model_validate_json(cached)
            except Exception:
                pass

        rule_result = self._rule_match(message)
        if rule_result.confidence >= 0.85:
            l1_cache.set(cache_key, rule_result.model_dump_json(), ttl_seconds=600)
            return rule_result

        llm_result = await self._llm_classify(message)
        result = llm_result or rule_result
        l1_cache.set(cache_key, result.model_dump_json(), ttl_seconds=600)
        return result

    def emergency_filter(self, message: str) -> IntentResult | None:
        normalized = message.lower()
        if any(keyword.lower() in normalized for keyword in EMERGENCY_KEYWORDS):
            return IntentResult(category="emergency", subcategory="urgent_response", confidence=1.0)
        return None

    def _rule_match(self, message: str) -> IntentResult:
        normalized = message.lower()
        scores: list[tuple[int, int, str, str]] = []
        for index, rule in enumerate(RULES):
            score = sum(1 for keyword in rule.keywords if keyword.lower() in normalized)
            if score:
                scores.append((score, -index, rule.category, rule.subcategory))
        if not scores:
            if any(keyword in message for keyword in CHITCHAT_KEYWORDS) or re.search(r"hello|hi|thanks", normalized):
                return IntentResult(category="chitchat", subcategory="", confidence=0.78)
            return IntentResult(category="other", subcategory="", confidence=0.45)

        score, _, category, subcategory = sorted(scores, reverse=True)[0]
        confidence = min(0.95, 0.65 + score * 0.15)
        return IntentResult(category=category, subcategory=subcategory, confidence=confidence)

    async def _llm_classify(self, message: str) -> IntentResult | None:
        if not settings.llm_api_key:
            return None

        prompt = (
            "你是医疗陪护平台的意图分类器。只输出 JSON，不要输出解释。\n"
            "category 只能是 medical_consult/platform_faq/chitchat/other。\n"
            "medical_consult 的 subcategory 只能是 symptom_inquiry/medication_consult/"
            "report_interpretation/disease_knowledge/care_method。\n"
            "platform_faq 的 subcategory 只能是 recruitment_process/account_verification/"
            "fee_cooperation/other_platform。\n"
            "chitchat 和 other 的 subcategory 为空字符串。\n"
            "confidence 是 0 到 1 的数字。\n"
            f"用户消息：{message}"
        )
        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return self._validate_llm_result(json.loads(content))
        except Exception:
            return None

    def _validate_llm_result(self, data: dict) -> IntentResult | None:
        category = str(data.get("category", "other"))
        subcategory = str(data.get("subcategory", ""))
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5

        if category not in TOP_LEVEL_CATEGORIES - {"emergency"}:
            return None
        if category == "medical_consult" and subcategory not in MEDICAL_SUBCATEGORIES:
            subcategory = "symptom_inquiry"
            confidence = min(confidence, 0.65)
        if category == "platform_faq" and subcategory not in PLATFORM_SUBCATEGORIES:
            subcategory = "other_platform"
            confidence = min(confidence, 0.65)
        if category in {"chitchat", "other"}:
            subcategory = ""
        return IntentResult(category=category, subcategory=subcategory, confidence=max(0, min(1, confidence)))
