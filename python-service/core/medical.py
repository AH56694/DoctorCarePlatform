"""Conservative routing signals; these are not a diagnostic classifier."""

import re

MEDICAL_TERMS = (
    "痛",
    "发烧",
    "发热",
    "咳嗽",
    "气短",
    "呼吸",
    "胸闷",
    "头晕",
    "晕倒",
    "昏迷",
    "出血",
    "呕吐",
    "腹泻",
    "恶心",
    "过敏",
    "皮疹",
    "麻木",
    "抽搐",
    "乏力",
    "不舒服",
    "症状",
    "疾病",
    "病史",
    "诊断",
    "治疗",
    "用药",
    "吃药",
    "药物",
    "药品",
    "剂量",
    "手术",
    "术后",
    "护理",
    "血压",
    "血糖",
    "血脂",
    "体温",
    "检查报告",
    "化验",
    "怀孕",
    "孕妇",
    "哺乳",
    "婴儿",
    "疫苗",
    "糖尿病",
    "高血压",
    "肿瘤",
    "感染",
    "抑郁",
    "自杀",
    "自伤",
    "抗生素",
    "阿司匹林",
    "布洛芬",
    "胰岛素",
    "窒息",
)
URGENT_TERMS = (
    "胸痛",
    "呼吸困难",
    "喘不过气",
    "意识不清",
    "昏迷",
    "大量出血",
    "抽搐",
    "自杀",
    "窒息",
)


def is_medical_text(text: str) -> bool:
    return any(term in text for term in MEDICAL_TERMS)


def user_statements(context: str, current: str) -> list[str]:
    """Only explicitly labelled user turns become facts; never assistant summaries."""
    history = re.findall(r"^(?:用户|user)\s*[:：]\s*(.*)$", context or "", flags=re.M | re.I)
    return [*history[-8:], current]


def urgent_signals(text: str) -> list[str]:
    # Avoid matching explicit denials and ordinary educational questions.
    if re.search(r"^(什么是|解释|科普|如何预防)", text.strip()):
        return []
    signals = []
    for term in URGENT_TERMS:
        for match in re.finditer(re.escape(term), text):
            prefix = text[max(0, match.start() - 6) : match.start()]
            if not re.search(r"(没有|并无|否认|无|不伴|未出现)[^，。；]{0,3}$", prefix):
                signals.append(term)
                break
    return signals
