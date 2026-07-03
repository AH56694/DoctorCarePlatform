from backend.app.services.rag_client import RagServiceClient


def test_rag_task_type_maps_to_medical_consult() -> None:
    intent = RagServiceClient()._intent_from_task_type("knowledge_qa")
    assert intent.category == "medical_consult"
    assert intent.subcategory == "rag_knowledge_qa"


def test_rag_sources_are_normalized() -> None:
    sources = RagServiceClient()._normalize_sources([{"doc": "术后护理指南", "content": "观察伤口渗出。"}])
    assert sources == [
        {
            "title": "术后护理指南",
            "snippet": "观察伤口渗出。",
            "source_url": "",
            "doc": "术后护理指南",
            "content": "观察伤口渗出。",
        }
    ]
