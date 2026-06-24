from dataclasses import dataclass


MEDICAL_SUBCATEGORIES = {
    "symptom_inquiry",
    "medication_consult",
    "report_interpretation",
    "disease_knowledge",
    "care_method",
}
PLATFORM_SUBCATEGORIES = {
    "recruitment_process",
    "account_verification",
    "fee_cooperation",
    "other_platform",
}

COLLECTIONS = {
    "symptom_inquiry": "medical.symptom_inquiry",
    "medication_consult": "medical.medication_consult",
    "report_interpretation": "medical.report_interpretation",
    "disease_knowledge": "medical.disease_knowledge",
    "care_method": "medical.care_method",
    "recruitment_process": "platform.recruitment_process",
    "account_verification": "platform.account_verification",
    "fee_cooperation": "platform.fee_cooperation",
    "other_platform": "platform.other_platform",
}

EMERGENCY_KEYWORDS = [
    "自杀",
    "不想活",
    "割腕",
    "胸痛",
    "呼吸困难",
    "昏迷",
    "大出血",
    "中风",
    "抽搐",
]


@dataclass(frozen=True)
class IntentRule:
    category: str
    subcategory: str
    keywords: tuple[str, ...]


RULES = [
    IntentRule("medical_consult", "medication_consult", ("用药", "吃药", "药物", "剂量", "副作用")),
    IntentRule("medical_consult", "report_interpretation", ("报告", "化验", "指标", "CT", "核磁", "B超")),
    IntentRule("medical_consult", "care_method", ("护理", "陪护", "压疮", "术后", "翻身", "照护")),
    IntentRule("medical_consult", "disease_knowledge", ("是什么病", "病因", "传染", "预防", "疾病")),
    IntentRule("medical_consult", "symptom_inquiry", ("疼", "痛", "发烧", "咳嗽", "头晕", "恶心")),
    IntentRule("platform_faq", "recruitment_process", ("招聘", "应聘", "简历", "面试", "接单")),
    IntentRule("platform_faq", "account_verification", ("认证", "账号", "实名", "登录", "注册")),
    IntentRule("platform_faq", "fee_cooperation", ("费用", "收费", "合作", "佣金", "提现")),
]
