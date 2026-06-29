from ai_service.app.domain.intents import COLLECTIONS
from ai_service.app.schemas import Citation, IntentResult
from ai_service.app.services.embedding_client import EmbeddingClient


DEMO_KNOWLEDGE: dict[str, list[Citation]] = {
    "medical.symptom_inquiry": [
        Citation(title="症状记录", snippet="记录症状出现时间、持续时长、严重程度、诱因、伴随表现和既往病史，有助于线下就诊沟通。"),
        Citation(title="就医提醒", snippet="持续高热、胸痛、呼吸困难、意识异常、大量出血等情况应尽快线下就医。"),
    ],
    "medical.medication_consult": [
        Citation(title="用药安全", snippet="药物剂量、频次和疗程应以医生处方或药品说明书为准，不建议自行叠加同类药物。"),
        Citation(title="不良反应", snippet="如出现皮疹、呼吸困难、明显头晕、严重胃肠不适等疑似不良反应，应及时联系医生。"),
    ],
    "medical.report_interpretation": [
        Citation(title="报告解读", snippet="检查报告需要结合症状、体征、年龄、既往病史和用药情况综合判断，单个指标不能直接等同诊断。"),
    ],
    "medical.disease_knowledge": [
        Citation(title="疾病科普", snippet="疾病知识问答仅用于健康教育，不能替代医生面诊、检查和诊断。"),
    ],
    "medical.care_method": [
        Citation(title="陪护照护", snippet="长期卧床者需定时翻身、保持皮肤清洁干燥，并观察压疮风险。"),
        Citation(title="术后护理", snippet="术后陪护应关注疼痛变化、伤口渗出、体温和活动耐受情况，异常时及时联系医护人员。"),
    ],
    "platform.recruitment_process": [
        Citation(title="招聘流程", snippet="患者发布招聘后，护理方可投递应聘；患者审核通过后系统会创建双方聊天会话。"),
        Citation(title="反向邀约", snippet="患者也可以从空闲护理方列表发起邀约，护理方接受后进入匹配沟通。"),
    ],
    "platform.account_verification": [
        Citation(title="账号认证", snippet="患者和护理方资料相互独立；护理方资质证书提交后由后台审核。"),
    ],
    "platform.fee_cooperation": [
        Citation(title="费用合作", snippet="费用可在招聘信息中说明，双方应在匹配后的聊天中确认服务时间、地点和结算方式。"),
    ],
    "platform.other_platform": [
        Citation(title="平台帮助", snippet="平台支持账号身份切换、招聘匹配、AI 问诊、短信通知和后台审核。"),
    ],
}


class RagRetriever:
    def __init__(self) -> None:
        self.embedding_client = EmbeddingClient()

    async def retrieve(self, query: str, intent: IntentResult, top_k: int = 3) -> list[Citation]:
        if not intent.subcategory:
            return []
        collection = COLLECTIONS.get(intent.subcategory, "")
        if not collection:
            return []

        try:
            await self.embedding_client.embed([query])
        except Exception:
            # The demo knowledge base remains available even when the embedding
            # service is offline. Production retrieval can replace this branch
            # with pgvector/Milvus/Qdrant search.
            pass
        return DEMO_KNOWLEDGE.get(collection, [])[:top_k]
