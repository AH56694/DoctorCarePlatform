import json
from unittest.mock import Mock

from core.llm import LLMService


class Doc:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}


def make_service_without_llm():
    service = LLMService.__new__(LLMService)
    service.llm = None
    service.fallback_providers = ["retrieval"]
    service.local_timeout = 1
    return service


def test_get_answer_uses_ollama_fallback_before_retrieval(monkeypatch):
    service = make_service_without_llm()
    service.fallback_providers = ["ollama", "retrieval"]

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": "这是本地模型生成的回答。"}
    post = Mock(return_value=response)
    monkeypatch.setattr("core.llm.requests.post", post)

    answer = service.get_answer("你好", [])

    assert answer == "这是本地模型生成的回答。"
    assert post.call_args[0][0].endswith("/api/generate")


def test_get_answer_falls_back_to_retrieved_docs_when_llm_unavailable():
    service = make_service_without_llm()
    docs = [
        Doc(
            "术后夜间疼痛明显时，应重点观察疼痛部位、疼痛评分、生命体征、切口渗血和用药后的缓解情况。",
            {"source": "术后护理指南.pdf", "page": 3, "chunk_index": 1},
        ),
        Doc(
            "老人术后还需要留意意识状态、呼吸情况、发热、活动受限和异常出血，必要时及时联系医生。",
            {"source": "术后护理指南.pdf", "page": 4, "chunk_index": 2},
        ),
    ]

    answer = service.get_answer("老人术后夜间疼痛明显，需要重点观察什么？", docs)

    assert "暂时无法回答" not in answer
    assert "重点结论" in answer
    assert "疼痛评分" in answer
    assert "生命体征" in answer
    assert "术后护理指南.pdf" in answer


def test_get_answer_stream_uses_token_events_for_fallback():
    service = make_service_without_llm()
    docs = [
        Doc(
            "夜间疼痛加重时，应观察疼痛强度、持续时间、伴随症状和镇痛药效果。",
            {"source": "疼痛护理规范.docx"},
        )
    ]

    events = [
        json.loads(chunk)
        for chunk in service.get_answer_stream("夜间疼痛加重怎么办？", docs)
    ]

    assert events[0]["type"] == "start"
    assert any(event["type"] == "token" for event in events)
    assert events[-1]["type"] == "end"
    assert not any(event["type"] == "error" for event in events)
    assert "暂时无法回答" not in events[-1]["content"]
    assert "疼痛护理规范.docx" in events[-1]["content"]
