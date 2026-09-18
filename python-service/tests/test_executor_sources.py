from agent.executor import Executor


def make_executor():
    return Executor.__new__(Executor)


def test_normalize_chunk_recovers_metadata_from_serialized_dict():
    executor = make_executor()
    raw_chunk = {
        "content": (
            "{'content': '术后夜间疼痛明显时，应观察疼痛评分、生命体征和切口渗血。', "
            "'metadata': {'source': '术后护理指南.pdf', 'doc_id': 12, 'page': 3, 'chunk_index': 1}}"
        ),
        "score": 0.72,
    }

    chunk = executor._normalize_chunk(raw_chunk)
    source = executor._source_from_chunk(chunk)

    assert chunk["content"] == "术后夜间疼痛明显时，应观察疼痛评分、生命体征和切口渗血。"
    assert chunk["metadata"]["source"] == "术后护理指南.pdf"
    assert source["title"] == "术后护理指南.pdf"
    assert source["doc_id"] == 12
    assert source["page"] == 3
    assert source["chunk_index"] == 1
    assert "生命体征" in source["snippet"]


def test_source_from_chunk_skips_empty_metadata():
    executor = make_executor()

    assert executor._source_from_chunk({"content": "无来源片段", "metadata": {}}) == {}


def test_search_uses_explicit_loop_query_instead_of_previous_rewrite(monkeypatch):
    from unittest.mock import Mock
    from agent.state import AgentState, StepType
    from agent.planner import Planner
    from tools.registry import tool_registry

    executor = make_executor()
    executor.planner = Planner()
    executor.vector_store = Mock()
    executor.vector_store.search.return_value = []
    monkeypatch.setattr(tool_registry, "has_tool", lambda name: False)
    state = AgentState(original_input="原始问题")
    state.add_intermediate_conclusion("old", "rewritten_question", "旧的查询")
    step = state.add_step(StepType.KNOWLEDGE_SEARCH, "knowledge_search", {"query": "新的补充查询"})
    executor._execute_knowledge_search(state, step)
    assert executor.vector_store.search.call_args.args[0] == "新的补充查询"


def test_answer_generation_uses_latest_search_not_first(monkeypatch):
    from unittest.mock import Mock
    from agent.state import AgentState, StepType
    from core.config import config

    executor = make_executor()
    executor.llm_service = Mock()
    executor.llm_service.get_answer.return_value = "新证据的回答"
    executor._memory_agent = Mock()
    monkeypatch.setattr(config, "RAG_STRICT_MODE", True)
    state = AgentState(original_input="头痛护理")
    state.add_step(StepType.MEMORY_READ, "memory_read").complete({"context": "已有历史"})
    state.add_step(StepType.KNOWLEDGE_SEARCH, "knowledge_search").complete({
        "chunks": [], "sources": [], "is_sufficient": False,
    })
    state.add_step(StepType.KNOWLEDGE_SEARCH, "knowledge_search").complete({
        "chunks": [{"content": "新证据", "metadata": {"source": "新指南"}}],
        "sources": [{"title": "新指南"}], "is_sufficient": True,
    })
    step = state.add_step(StepType.ANSWER_GENERATION, "answer_generation")
    result = executor._execute_answer_generation(state, step)
    assert result["answer"] == "新证据的回答"
    assert executor.llm_service.get_answer.call_args.args[1][0].page_content == "新证据"
