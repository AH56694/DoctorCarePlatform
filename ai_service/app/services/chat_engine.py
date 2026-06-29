import httpx

from ai_service.app.core.config import settings
from ai_service.app.schemas import ChatRequest, ChatResponse, Citation, IntentResult
from ai_service.app.services.cache import (
    cache_hash,
    dumps_cache_payload,
    l1_cache,
    l2_cache,
    loads_cache_payload,
    normalize_text,
)
from ai_service.app.services.intent_classifier import IntentClassifier
from ai_service.app.services.rag import RagRetriever


MEDICAL_DISCLAIMER = "提示：以下内容仅用于健康咨询和陪护沟通参考，不能替代医生诊断或线下就医。"


class ChatEngine:
    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.rag = RagRetriever()

    async def answer(self, request: ChatRequest) -> ChatResponse:
        message = normalize_text(request.message)
        emergency = self.intent_classifier.emergency_filter(message)
        if emergency:
            return self._urgent_response(emergency)

        intent = await self.intent_classifier.classify(message)
        cached = await self._read_cached_answer(message, intent)
        if cached:
            return cached

        if intent.confidence < settings.intent_confidence_threshold:
            return ChatResponse(
                answer=(
                    "我想先确认一下：你是想咨询症状、用药、检查报告、疾病知识、护理方法，"
                    "还是想了解平台招聘、认证或费用流程？补充场景后我可以更准确地帮你梳理。"
                ),
                intent=intent,
                cache_hit_level="miss",
            )

        citations = await self.rag.retrieve(message, intent)
        answer = await self._generate_answer(message, intent, citations)
        answer = self._post_process_answer(answer, intent)

        response = ChatResponse(answer=answer, intent=intent, citations=citations, cache_hit_level="miss")
        await self._write_cache(message, response)
        return response

    def _urgent_response(self, intent: IntentResult) -> ChatResponse:
        return ChatResponse(
            answer=(
                "你描述的情况可能存在紧急风险。请立即联系当地急救电话或前往急诊。"
                "如果身边有人，请马上请对方陪同并保持电话畅通。"
                "在等待救助时，尽量保持安全体位，不要自行服用不确定的药物。"
            ),
            intent=intent,
            cache_hit_level="bypass",
        )

    async def _read_cached_answer(self, message: str, intent: IntentResult) -> ChatResponse | None:
        if intent.category not in {"platform_faq", "chitchat"}:
            return None
        key = self._answer_cache_key(message, intent)
        value = l1_cache.get(key)
        level = "L1"
        if value is None:
            value = await l2_cache.get(key)
            level = "L2"
        if value is None:
            return None
        payload = loads_cache_payload(value)
        if not payload:
            return None
        try:
            return ChatResponse(
                answer=str(payload["answer"]),
                intent=intent,
                cache_hit_level=level,
                citations=[Citation.model_validate(item) for item in payload.get("citations", [])],
            )
        except Exception:
            return None

    async def _write_cache(self, message: str, response: ChatResponse) -> None:
        if response.intent.category not in {"platform_faq", "chitchat"}:
            return
        key = self._answer_cache_key(message, response.intent)
        payload = dumps_cache_payload(
            {
                "answer": response.answer,
                "citations": [citation.model_dump() for citation in response.citations],
            }
        )
        l1_cache.set(key, payload, ttl_seconds=600)
        await l2_cache.set(key, payload, ttl_seconds=3600)

    def _answer_cache_key(self, message: str, intent: IntentResult) -> str:
        return f"answer:{intent.category}:{intent.subcategory}:{cache_hash(message)}"

    async def _generate_answer(self, message: str, intent: IntentResult, citations: list[Citation]) -> str:
        llm_answer = await self._llm_generate(message, intent, citations)
        if llm_answer:
            return llm_answer
        return self._compose_fallback_answer(message, intent, citations)

    async def _llm_generate(self, message: str, intent: IntentResult, citations: list[Citation]) -> str | None:
        if not settings.llm_api_key:
            return None
        context = "\n".join(f"- {item.title}: {item.snippet}" for item in citations) or "无检索片段"
        prompt = (
            "你是 AI 医疗陪护平台的问答助手。请根据用户问题、意图和检索片段回答。\n"
            "要求：医疗问题必须提醒不能替代医生诊断；遇到危险信号建议线下就医；"
            "平台问题直接说明流程；不要编造不存在的功能。\n"
            f"意图：{intent.category}/{intent.subcategory}\n"
            f"检索片段：\n{context}\n"
            f"用户问题：{message}"
        )
        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"]).strip()
        except Exception:
            return None

    def _compose_fallback_answer(self, message: str, intent: IntentResult, citations: list[Citation]) -> str:
        context = " ".join(item.snippet for item in citations)
        if intent.category == "medical_consult":
            if intent.subcategory == "symptom_inquiry":
                return (
                    f"结合你的描述“{message}”，建议先记录症状出现时间、持续多久、严重程度、伴随表现、"
                    f"既往病史和正在使用的药物。{context} 如果症状加重或出现危险信号，请尽快线下就医。"
                )
            if intent.subcategory == "medication_consult":
                return (
                    f"关于用药问题“{message}”，请优先以医生处方或药品说明书为准。{context} "
                    "如果不确定剂量、漏服处理或是否能同服，请联系开药医生或药师确认。"
                )
            if intent.subcategory == "report_interpretation":
                return (
                    f"检查报告需要结合症状、体征和既往病史一起看。{context} "
                    "你可以补充报告项目、异常指标、参考范围和当前症状，我再帮你整理就诊沟通要点。"
                )
            if intent.subcategory == "care_method":
                return (
                    f"护理场景中可以先明确照护对象的活动能力、伤口/管路情况、饮食和排泄情况。{context} "
                    "如出现发热、伤口明显渗出、疼痛加重或意识异常，应及时联系医护人员。"
                )
            return f"{context} 这类疾病知识仅作科普参考，具体诊断和治疗仍需医生结合检查判断。"
        if intent.category == "platform_faq":
            return context or "平台支持患者发布招聘、护理方投递应聘、患者反向邀约、匹配后聊天、互评和短信通知。"
        if intent.category == "chitchat":
            return "我在。你可以直接说现在最困扰你的问题，我会帮你把下一步要做什么梳理清楚。"
        return "这个问题我还不能准确分类。请补充对象、场景、症状或你希望解决的具体事项。"

    def _post_process_answer(self, answer: str, intent: IntentResult) -> str:
        if intent.category == "medical_consult" and MEDICAL_DISCLAIMER not in answer:
            return f"{MEDICAL_DISCLAIMER}\n\n{answer}"
        return answer
