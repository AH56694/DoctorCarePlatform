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
TOP_LEVEL_CATEGORIES = {"medical_consult", "platform_faq", "chitchat", "other", "emergency"}

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

EMERGENCY_KEYWORDS = (
    "自杀",
    "不想活",
    "割腕",
    "服毒",
    "胸痛",
    "呼吸困难",
    "昏迷",
    "大量出血",
    "中风",
    "抽搐",
    "意识不清",
    "严重过敏",
    "休克",
    # Common mojibake strings kept for legacy tests and incorrectly encoded input.
    "鑷潃",
    "涓嶆兂娲",
    "鑳哥棝",
    "鍛煎惛鍥伴毦",
)

CHITCHAT_KEYWORDS = ("你好", "谢谢", "在吗", "辛苦", "陪我聊", "焦虑", "害怕")


@dataclass(frozen=True)
class IntentRule:
    category: str
    subcategory: str
    keywords: tuple[str, ...]


RULES = [
    IntentRule(
        "medical_consult",
        "medication_consult",
        (
            "用药",
            "吃药",
            "药物",
            "剂量",
            "副作用",
            "漏服",
            "禁忌",
            "medication",
            "medicine",
            "dose",
            "side effect",
            "side effects",
            "鑽",
            "鍓傞噺",
            "鍓綔",
        ),
    ),
    IntentRule(
        "medical_consult",
        "report_interpretation",
        ("报告", "化验", "指标", "CT", "核磁", "B超", "血常规", "尿检", "report", "lab", "indicator", "鎶ュ憡", "鎸囨爣"),
    ),
    IntentRule(
        "medical_consult",
        "care_method",
        ("护理", "陪护", "压疮", "术后", "翻身", "照护", "康复", "换药", "care", "nursing", "rehab", "鎶ょ悊", "闄姢"),
    ),
    IntentRule(
        "medical_consult",
        "disease_knowledge",
        ("是什么病", "病因", "传染", "预防", "疾病", "并发症", "病程", "鐤剧梾"),
    ),
    IntentRule(
        "medical_consult",
        "symptom_inquiry",
        ("疼", "痛", "发烧", "咳嗽", "头晕", "恶心", "腹泻", "乏力", "皮疹", "pain", "fever", "cough", "dizzy", "鐥", "鍙戠儳"),
    ),
    IntentRule(
        "platform_faq",
        "recruitment_process",
        (
            "发布招聘",
            "选择护理人员",
            "招聘",
            "应聘",
            "简历",
            "面试",
            "接单",
            "邀约",
            "匹配",
            "job",
            "apply",
            "caregiver",
            "invite",
            "match",
            "鎷涜仒",
            "搴旇仒",
        ),
    ),
    IntentRule(
        "platform_faq",
        "account_verification",
        ("认证", "账号", "实名", "登录", "注册", "证书", "审核", "璁よ瘉", "璐﹀彿"),
    ),
    IntentRule(
        "platform_faq",
        "fee_cooperation",
        ("费用", "收费", "合作", "佣金", "提现", "支付", "退款", "璐圭敤", "鏀惰垂"),
    ),
]
