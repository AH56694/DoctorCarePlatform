import json
import re

import httpx

from ai_service.app.core.config import settings
from ai_service.app.domain.intents import EMERGENCY_KEYWORDS, RULES
from ai_service.app.schemas import IntentResult


class IntentClassifier:
    async def classify(self, message: str) -> IntentResult:
        emergency = self._emergency_filter(message)
        if emergency:
            return emergency

        rule_result = self._rule_match(message)
        if rule_result.confidence >= 0.85:
            return rule_result

        llm_result = await self._llm_classify(message)
        return llm_result or rule_result

    def _emergency_filter(self, message: str) -> IntentResult | None:
        if any(keyword.lower() in message.lower() for keyword in EMERGENCY_KEYWORDS):
            return IntentResult(category="emergency", subcategory="urgent_response", confidence=1.0)
        return None

    def _rule_match(self, message: str) -> IntentResult:
        scores: list[tuple[int, str, str]] = []
        for rule in RULES:
            score = sum(1 for keyword in rule.keywords if keyword.lower() in message.lower())
            if score:
                scores.append((score, rule.category, rule.subcategory))
        if not scores:
            if re.search(r"你好|谢谢|在吗|辛苦", message):
                return IntentResult(category="chitchat", subcategory="", confidence=0.78)
            return IntentResult(category="other", subcategory="", confidence=0.45)

        score, category, subcategory = sorted(scores, reverse=True)[0]
        confidence = min(0.95, 0.65 + score * 0.15)
        return IntentResult(category=category, subcategory=subcategory, confidence=confidence)

    async def _llm_classify(self, message: str) -> IntentResult | None:
        if not settings.llm_api_key:
            return None

        prompt = (
            "你是医疗陪护平台的意图分类器。只输出JSON。"
            "category只能是medical_consult/platform_faq/chitchat/other；"
            "medical_consult子类只能是symptom_inquiry/medication_consult/"
            "report_interpretation/disease_knowledge/care_method；"
            "platform_faq子类只能是recruitment_process/account_verification/"
            "fee_cooperation/other_platform。"
            f"用户消息：{message}"
        )
        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return IntentResult.model_validate(data)
