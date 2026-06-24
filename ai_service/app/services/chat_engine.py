from ai_service.app.core.config import settings
from ai_service.app.schemas import ChatRequest, ChatResponse, IntentResult
from ai_service.app.services.cache import l1_cache
from ai_service.app.services.intent_classifier import IntentClassifier
from ai_service.app.services.rag import RagRetriever


class ChatEngine:
    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.rag = RagRetriever()

    async def answer(self, request: ChatRequest) -> ChatResponse:
        intent = await self.intent_classifier.classify(request.message)
        if intent.category == "emergency":
            return ChatResponse(
                answer=(
                    "你描述的情况可能存在紧急风险。请立即联系当地急救电话或前往急诊，"
                    "如果身边有人，请马上请对方陪同并保持电话畅通。"
                ),
                intent=intent,
                cache_hit_level="bypass",
            )

        if intent.confidence < settings.intent_confidence_threshold:
            return ChatResponse(
                answer="我想先确认一下：您是想咨询症状/用药/报告，还是想了解平台招聘、认证或费用流程？",
                intent=intent,
                cache_hit_level="miss",
            )

        cache_key = f"{intent.category}:{intent.subcategory}:{request.message}"
        cached = l1_cache.get(cache_key)
        if cached and intent.category in {"platform_faq", "chitchat"}:
            return ChatResponse(answer=cached, intent=intent, cache_hit_level="L1")

        citations = await self.rag.retrieve(request.message, intent)
        answer = self._compose_answer(request.message, intent, citations)
        if intent.category in {"platform_faq", "chitchat"}:
            l1_cache.set(cache_key, answer)
        return ChatResponse(answer=answer, intent=intent, citations=citations)

    def _compose_answer(self, message: str, intent: IntentResult, citations: list) -> str:
        if intent.category == "medical_consult":
            context = " ".join(item.snippet for item in citations)
            return (
                "以下内容仅用于健康咨询和陪护参考，不能替代医生诊断。"
                f"结合你的描述“{message}”，建议先记录症状持续时间、严重程度、伴随表现和既往病史。"
                f"{context} 如症状加重或出现急性危险信号，请尽快线下就医。"
            )
        if intent.category == "platform_faq":
            context = " ".join(item.snippet for item in citations)
            return f"关于平台问题：{context or '目前可先完成账号资料，再根据角色进入招聘或应聘流程。'}"
        if intent.category == "chitchat":
            return "我在的。你可以直接说现在最困扰你的问题，我会尽量帮你梳理下一步。"
        return "这个问题我还不太确定分类。你可以补充一下场景、对象和你希望解决的具体问题。"
