from unittest.mock import Mock

from agent.executor import Executor
from agent.state import AgentState, StepType
from tools.knowledge_search import KnowledgeSearchTool
from core.vector_store import VectorStoreManager
from core.llm import LLMService


class _Document:
    def __init__(self, content: str, metadata: dict):
        self.page_content = content
        self.metadata = metadata


def test_knowledge_search_preserves_real_retrieval_scores():
    tool = KnowledgeSearchTool.__new__(KnowledgeSearchTool)
    tool.vector_store = Mock()
    tool.vector_store.search.return_value = [
        _Document(
            "术后应观察生命体征。",
            {"source": "护理指南", "score": 0.82, "vector_score": 0.82, "rerank_score": 0.6},
        )
    ]

    result = tool.execute({"query": "术后观察", "top_k": 1})

    assert result["scores"] == [0.82]
    assert result["chunks"][0]["vector_score"] == 0.82
    assert result["chunks"][0]["rerank_score"] == 0.6


def test_answer_generation_does_not_load_memory_twice():
    executor = Executor.__new__(Executor)
    executor._memory_agent = Mock()
    executor.llm_service = Mock()
    executor.llm_service.get_answer.return_value = "回答"

    state = AgentState(
        conversation_id="conversation-1",
        original_input="继续观察什么？",
        context="用户: 上一轮描述术后疼痛",
    )
    memory_step = state.add_step(StepType.MEMORY_READ, "memory_read")
    memory_step.complete({"context": state.context, "has_history": True})
    answer_step = state.add_step(StepType.ANSWER_GENERATION, "answer_generation")

    executor._execute_answer_generation(state, answer_step)

    executor._memory_agent.load_memory.assert_not_called()
    assert executor.llm_service.get_answer.call_args.args[2] == state.context


def test_l2_distance_is_normalized_to_similarity(monkeypatch):
    from core.config import config

    manager = VectorStoreManager.__new__(VectorStoreManager)
    monkeypatch.setattr(config, "VECTOR_STORE_METRIC_TYPE", "L2")

    assert manager._normalize_vector_score(1.0) == 0.5


def test_prompt_context_layers_respect_total_character_budget(monkeypatch):
    from core.config import config

    service = LLMService.__new__(LLMService)
    monkeypatch.setattr(config, "LLM_QUESTION_MAX_CHARS", 100)
    monkeypatch.setattr(config, "LLM_CONVERSATION_CONTEXT_MAX_CHARS", 100)
    monkeypatch.setattr(config, "LLM_KNOWLEDGE_CONTEXT_MAX_CHARS", 100)
    monkeypatch.setattr(config, "LLM_PROMPT_MAX_CHARS", 2750)
    docs = [_Document("k" * 500, {"source": "guide"})]

    question, knowledge, conversation = service._prepare_prompt_inputs(
        "q" * 500,
        docs,
        "c" * 500,
    )

    assert len(question) == 100
    assert len(conversation) <= 100
    assert len(question) + len(knowledge) + len(conversation) <= 250
