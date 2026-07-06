from workflows.knowledge_qa_agent import KnowledgeQAAgent


class _NoDocsVectorStore:
    def search(self, **kwargs):
        return []


class _FailingLLM:
    def get_answer(self, *args, **kwargs):
        raise AssertionError("LLM should not be called without sufficient evidence")


def _agent_for_safety_tests() -> KnowledgeQAAgent:
    agent = object.__new__(KnowledgeQAAgent)
    agent.vector_store = _NoDocsVectorStore()
    agent.llm_service = _FailingLLM()
    agent.strict_rag = True
    agent.similarity_threshold = 0.68
    agent.top_k = 5
    agent.use_rerank = True
    agent.min_source_count = 1
    agent._save_to_memory = lambda *args, **kwargs: None
    return agent


def test_l1_without_sources_returns_insufficient_evidence_answer() -> None:
    agent = _agent_for_safety_tests()

    result = agent._ask_l1("头痛应该吃什么药？", conversation_id=None, full_context="")

    assert result["has_sources"] is False
    assert result["sources"] == []
    assert "不能基于猜测给出诊断、用药或治疗结论" in result["answer"]


def test_empty_metadata_does_not_count_as_traceable_source() -> None:
    agent = _agent_for_safety_tests()
    doc = type("Doc", (), {"metadata": {}, "score": 0.9})()

    sources = agent._build_sources([doc])

    assert sources == []
    assert agent._sources_are_sufficient(sources) is False
