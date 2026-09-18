import json
import time
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent.consultation import (
    AnswerDraft,
    ConsultationPlanner,
    Decision,
    EvidenceReview,
    PatientAssessment,
)
from agent.orchestrator import Orchestrator
from agent.policies import policies
from agent.state import AgentState, AgentStatus, StepType
from core.config import config
from core.llm import LLMService
from intent.classifier import IntentClassifier, IntentType

QUESTION = "我35岁，头痛三天，需要观察什么？"
DOCUMENT = {
    "content": "头痛时记录持续时间和伴随症状，并联系医生评估。",
    "metadata": {"source": "审核过的护理指南", "doc_id": 42},
    "score": 0.9,
}


class ScriptedModel:
    def __init__(self, actions=None, reviews=None, verification=True):
        self.actions = list(
            actions or [{"action": "search", "query": "头痛观察"}, {"action": "answer"}]
        )
        self.reviews = list(reviews or [{"relevant_ids": ["S1"], "sufficient": True}])
        self.verification = verification
        self.prompts = []

    def generate_structured(self, prompt, schema):
        self.prompts.append((schema.__name__, prompt))
        if schema is PatientAssessment:
            data = {"is_medical": True, "personal": True}
        elif schema is Decision:
            data = self.actions.pop(0) if self.actions else {"action": "escalate"}
        elif schema is EvidenceReview:
            data = self.reviews.pop(0) if self.reviews else {"sufficient": False}
        elif schema is AnswerDraft:
            data = {"claims": [{"text": "记录头痛持续时间和伴随症状。", "source_ids": ["S1"]}]}
        else:
            data = {"safe": self.verification, "supported_claims": [0] if self.verification else []}
        return schema.model_validate(data)


class FakeExecutor:
    def __init__(self, documents=None, context=""):
        self.documents = documents if documents is not None else [DOCUMENT]
        self.context = context
        self.calls = []
        self.memory_agent = SimpleNamespace(save_memory=Mock(return_value=True))

    def execute_step(self, state, step):
        self.calls.append((step.step_name, step.input_data))
        if step.step_type == StepType.MEMORY_READ:
            state.context += self.context
            step.complete({"context": self.context})
        elif step.step_type == StepType.KNOWLEDGE_SEARCH:
            step.complete({"chunks": self.documents, "scores": [0.9] * len(self.documents)})
        else:
            raise AssertionError(f"Unexpected tool: {step.step_name}")


def make_agent(model=None, executor=None):
    agent = Orchestrator.__new__(Orchestrator)
    agent.executor = executor or FakeExecutor()
    agent.consultation = ConsultationPlanner(model or ScriptedModel())
    agent.event_bus = Mock()
    agent.policies = policies
    agent._states = {}
    return agent


@pytest.mark.parametrize("question", ["我胸痛", "我发烧了", "头痛三天", "你好，我呼吸困难"])
def test_short_medical_inputs_never_become_chitchat(question):
    classifier = IntentClassifier()
    classifier._llm_service = False
    assert classifier.classify(question).intent is IntentType.KNOWLEDGE_QA


def test_observations_change_the_next_search_and_only_final_sources_are_used():
    model = ScriptedModel(
        actions=[
            {"action": "search", "query": "头痛"},
            {"action": "search", "query": "头痛持续三天伴随症状观察"},
            {"action": "answer"},
        ],
        reviews=[
            {"relevant_ids": [], "sufficient": False, "missing_aspects": ["伴随症状"]},
            {"relevant_ids": ["S1"], "sufficient": True},
        ],
    )
    agent = make_agent(model)
    result = agent.run(QUESTION, conversation_id="c1", run_id="r1")
    state = agent.get_state("r1")
    assert result["stop_reason"] == "answered"
    assert len(state.searched_queries) == 2
    decisions = [prompt for schema, prompt in model.prompts if schema == "Decision"]
    assert '"missing_aspects": ["伴随症状"]' in decisions[1]
    assert '"is_sufficient": true' in decisions[2]
    assert "[S1]" in result["answer"]
    assert result["sources"][0]["doc_id"] == 42
    agent.executor.memory_agent.save_memory.assert_called_once()
    assert agent.executor.memory_agent.save_memory.call_args.args[2] == result["answer"]
    assert state.steps[-1].step_name == "memory_write"


def test_stream_and_sync_share_final_answer_and_waiting_contract():
    sync = make_agent().run(QUESTION, run_id="sync")
    agent = make_agent()
    events = [json.loads(event) for event in agent.run_stream(QUESTION, run_id="stream")]
    assert events[-1]["type"] == "end"
    assert events[-1]["content"]["answer"] == sync["answer"]
    assert (
        "".join(event["content"] for event in events if event["type"] == "token") == sync["answer"]
    )
    assert agent.get_state("stream").status == AgentStatus.COMPLETED


def test_clarification_is_saved_and_next_turn_reuses_user_facts_only():
    agent = make_agent()
    first = agent.run("我头痛", conversation_id="c1", run_id="first")
    assert first["requires_input"]
    assert "年龄" in first["answer"]
    assert agent.get_state("first").status == AgentStatus.WAITING
    assert not agent.get_state("first").searched_queries
    agent.executor.memory_agent.save_memory.assert_called_once()
    # Assistant assertions must never become patient facts.
    history = "用户: 我头痛\nAI: 患者80岁，已经持续十年，有糖尿病。\n"
    second = agent.run("35岁，三天了", context=history, conversation_id="c1", run_id="second")
    patient = agent.get_state("second").patient
    assert not second["requires_input"]
    assert {fact["value"] for fact in patient["facts"]} == {"35岁", "三天"}
    assert patient["is_medical"]


def test_urgent_symptom_short_circuits_before_any_llm_or_retrieval():
    model = ScriptedModel()
    agent = make_agent(model)
    result = agent.run("我胸痛，而且呼吸困难", run_id="urgent")
    assert result["stop_reason"] == "urgent_risk"
    assert "急诊" in result["answer"]
    assert not model.prompts
    assert not agent.executor.calls


def test_denied_urgent_symptom_does_not_trigger_emergency_rule():
    from core.medical import urgent_signals

    assert urgent_signals("我没有胸痛，无呼吸困难") == []


@pytest.mark.parametrize("query", ["头痛", " 头 痛！！！ "])
def test_repeated_queries_stop_without_another_tool_call(query):
    model = ScriptedModel(
        actions=[{"action": "search", "query": "头痛"}, {"action": "search", "query": query}],
        reviews=[{"sufficient": False}],
    )
    agent = make_agent(model)
    result = agent.run(QUESTION, run_id="repeat")
    assert result["stop_reason"] == "repeated_query"
    assert len(agent.get_state("repeat").searched_queries) == 1


def test_search_budget_and_decision_budget_are_enforced(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MAX_SEARCHES", 2)
    model = ScriptedModel(
        actions=[{"action": "search", "query": f"头痛{i}"} for i in range(4)],
        reviews=[{"sufficient": False}] * 3,
    )
    agent = make_agent(model)
    assert agent.run(QUESTION, run_id="limited")["stop_reason"] == "search_limit"
    assert len(agent.get_state("limited").searched_queries) == 2
    monkeypatch.setattr(config, "AGENT_MAX_DECISIONS", 1)
    assert make_agent().run(QUESTION)["stop_reason"] == "decision_limit"


def test_model_cannot_answer_without_evidence():
    agent = make_agent(ScriptedModel(actions=[{"action": "answer"}]))
    result = agent.run(QUESTION)
    assert result["stop_reason"] == "answer_without_evidence"
    assert not result["sources"]


def test_unverified_draft_never_leaks_to_sse_or_final_answer():
    agent = make_agent(ScriptedModel(verification=False))
    events = [json.loads(event) for event in agent.run_stream(QUESTION)]
    text = json.dumps(events, ensure_ascii=False)
    assert "记录头痛持续时间和伴随症状。" not in text
    assert events[-1]["content"]["sources"] == []


@pytest.mark.parametrize(
    "review",
    [
        {"relevant_ids": ["invented"], "sufficient": True},
        {"relevant_ids": ["S1"], "sufficient": True, "conflicts": ["不同适用人群"]},
        {"relevant_ids": [], "sufficient": True},
    ],
)
def test_evidence_gate_rejects_invalid_ids_conflicts_and_empty_support(review):
    agent = make_agent(ScriptedModel(reviews=[review]))
    result = agent.run(QUESTION, run_id="bad-evidence")
    assert not agent.get_state("bad-evidence").evidence["is_sufficient"]
    assert result["sources"] == []


def test_empty_and_untraceable_evidence_fail_closed():
    for docs in ([], [{"content": "头痛的护理资料", "metadata": {}, "score": 0.99}]):
        agent = make_agent(executor=FakeExecutor(documents=docs))
        assert agent.run(QUESTION)["sources"] == []


def test_no_model_asks_for_missing_information_then_declines_without_evidence():
    service = LLMService.__new__(LLMService)
    service.llm = None
    service.fallback_providers = ["retrieval"]
    agent = make_agent(service)
    assert agent.run("头痛三天")["requires_input"]
    result = agent.run(QUESTION)
    assert not result["sources"]
    assert result["stop_reason"] == "insufficient_evidence"


def test_late_worker_cannot_overwrite_timed_out_state(monkeypatch):
    release = Event()
    finished = Event()
    agent = make_agent()

    def slow_assess(state):
        release.wait(2)
        state.patient = {"late": True}
        finished.set()
        return state.patient

    agent.consultation.assess = slow_assess
    monkeypatch.setattr(config, "AGENT_STEP_TIMEOUT_SECONDS", 0.02)
    start = time.monotonic()
    result = agent.run(QUESTION, run_id="late")
    assert time.monotonic() - start < 0.5
    assert result["stop_reason"] == "timeout"
    release.set()
    assert finished.wait(1)
    assert "late" not in agent.get_state("late").patient
    assert agent.get_state("late").status == AgentStatus.COMPLETED


def test_step_limit_does_not_report_an_answer(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MAX_STEPS", 2)
    agent = make_agent()
    assert agent.run(QUESTION, run_id="steps")["stop_reason"] == "step_limit"
    assert len(agent.get_state("steps").steps) == 2


def test_interrupt_discards_the_pending_step():
    agent = make_agent()
    stream = agent.run_stream(QUESTION, run_id="cancel")
    assert json.loads(next(stream))["type"] == "step_started"
    assert agent.interrupt("cancel")
    events = [json.loads(event) for event in stream]
    assert events[-1]["type"] == "error"
    assert agent.get_state("cancel").status == AgentStatus.INTERRUPTED


def test_new_run_has_no_shared_patient_or_evidence_state():
    agent = make_agent()
    agent.run(QUESTION, run_id="a")
    agent.run("你好", run_id="b")
    assert agent.get_state("b").patient == {}
    assert agent.get_state("b").evidence == {}
    assert agent.get_state("a").evidence["documents"]


def test_structured_model_rejects_unknown_actions_and_wrong_types():
    service = LLMService.__new__(LLMService)
    for output in (
        '{"action":"delete_database"}',
        '{"action":"search","query":123}',
        '{"action":"search","query":"x","tool":"shell"}',
        "not json",
    ):
        service.generate = Mock(return_value=output)
        assert service.generate_structured("test", Decision) is None
    service.generate = Mock(return_value='```json\n{"action":"search","query":"头痛"}\n```')
    assert service.generate_structured("test", Decision).query == "头痛"


def test_high_score_irrelevant_snippet_fails_preliminary_gate():
    from agent.planner import Planner

    result = Planner().evaluate_retrieval_sufficiency(
        [{"content": "数据库索引优化教程"}],
        "胸痛持续三小时",
        [0.99],
    )
    assert not result.is_sufficient


def test_model_fact_without_matching_user_quote_is_discarded():
    model = Mock()
    model.generate_structured.return_value = PatientAssessment(
        is_medical=True,
        personal=True,
        facts=[{"field": "history", "value": "糖尿病", "quote": "有糖尿病", "turn": 0}],
    )
    state = AgentState(original_input=QUESTION)
    patient = ConsultationPlanner(model).assess(state)
    assert all(fact["value"] != "糖尿病" for fact in patient["facts"])


def test_empty_medical_history_does_not_force_personal_questions_for_education():
    model = Mock()
    model.generate_structured.return_value = PatientAssessment(is_medical=True, personal=False)
    state = AgentState(original_input="介绍头痛的常见原因")
    patient = ConsultationPlanner(model).assess(state)
    assert not patient["personal"]
    assert patient["missing_information"] == []


def test_clarification_stream_has_a_final_answer_and_memory_failure_is_visible():
    agent = make_agent()
    agent.executor.memory_agent.save_memory.return_value = False
    events = [json.loads(frame) for frame in agent.run_stream("我头痛", conversation_id="c")]
    end = events[-1]["content"]
    assert end["status"] == "waiting"
    assert end["answer"] == "".join(e["content"] for e in events if e["type"] == "token")
    assert end["memory_saved"] is False


@pytest.mark.parametrize("provider", ["ollama", "openai_compatible"])
def test_structured_decision_uses_configured_fallback_provider(provider, monkeypatch):
    service = LLMService.__new__(LLMService)
    service.llm = None
    service.fallback_providers = [provider]
    service.local_timeout = 1
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_BASE_URL", "https://model.example.invalid")
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_MODEL", "test-model")
    text = '{"action":"search","query":"头痛观察"}'
    response = Mock()
    response.json.return_value = {"response": text, "choices": [{"message": {"content": text}}]}
    post = Mock(return_value=response)
    monkeypatch.setattr("core.llm.requests.post", post)
    result = service.generate_structured("test", Decision)
    assert result.action == "search"
    assert post.call_count == 1


def test_semantic_review_observes_question_and_document_not_only_score():
    model = Mock()
    model.generate_structured.return_value = EvidenceReview(sufficient=False)
    planner = ConsultationPlanner(model)
    state = AgentState(original_input="胸痛的可能原因")
    evidence = planner.evaluate(
        state,
        {
            "chunks": [
                {
                    "content": "数据库索引优化教程",
                    "metadata": {"source": "数据库教材"},
                    "score": 0.99,
                }
            ]
        },
    )
    prompt = model.generate_structured.call_args.args[0]
    assert "胸痛的可能原因" in prompt and "数据库索引优化教程" in prompt
    assert not evidence["is_sufficient"]


def test_structured_prompt_budget_prevents_oversized_model_calls(monkeypatch):
    service = LLMService.__new__(LLMService)
    service.generate = Mock()
    monkeypatch.setattr(config, "LLM_PROMPT_MAX_CHARS", 1000)
    assert service.generate_structured("x" * 1001, Decision) is None
    service.generate.assert_not_called()
