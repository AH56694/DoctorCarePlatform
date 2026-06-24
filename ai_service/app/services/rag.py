from ai_service.app.domain.intents import COLLECTIONS
from ai_service.app.schemas import Citation, IntentResult
from ai_service.app.services.embedding_client import EmbeddingClient


DEMO_KNOWLEDGE = {
    "medical.symptom_inquiry": [
        Citation(title="症状初步咨询", snippet="持续高热、胸痛、呼吸困难等情况应尽快线下就医。")
    ],
    "medical.medication_consult": [
        Citation(title="用药安全", snippet="用药剂量需遵医嘱，避免自行叠加同类药物。")
    ],
    "medical.report_interpretation": [
        Citation(title="报告解读", snippet="检查报告需要结合症状、体征和既往病史综合判断。")
    ],
    "medical.disease_knowledge": [
        Citation(title="疾病知识", snippet="疾病科普仅作参考，不能替代医生诊断。")
    ],
    "medical.care_method": [
        Citation(title="护理方法", snippet="长期卧床者需定时翻身、保持皮肤清洁并观察压疮风险。")
    ],
    "platform.recruitment_process": [
        Citation(title="招聘流程", snippet="护理人员可提交资料、完成认证后参与岗位匹配。")
    ],
}


class RagRetriever:
    def __init__(self) -> None:
        self.embedding_client = EmbeddingClient()

    async def retrieve(self, query: str, intent: IntentResult) -> list[Citation]:
        if not intent.subcategory:
            return []
        collection = COLLECTIONS.get(intent.subcategory, "")
        if not collection:
            return []

        try:
            await self.embedding_client.embed([query])
        except Exception:
            pass
        return DEMO_KNOWLEDGE.get(collection, [])[:3]
