"""A bounded observe/decide/act loop shared by synchronous and SSE requests."""

import json
import logging
import re
import time
import uuid
from copy import deepcopy

from core.call_budget import call_with_timeout
from core.config import config
from core.medical import urgent_signals

from agent.consultation import ESCALATION, INSUFFICIENT, AnswerDraft, ConsultationPlanner
from agent.events import (
    EventBus,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepStartedEvent,
)
from agent.executor import Executor
from agent.planner import Planner
from agent.policies import policies
from agent.state import AgentState, AgentStatus, StepType

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.planner = Planner()
        self.executor = Executor()
        self.consultation = ConsultationPlanner(self.executor.llm_service)
        self.event_bus = EventBus()
        self.policies = policies
        self._states = {}

    def create_state(
        self, input_text, conversation_id=None, user_id=None, goal=None, run_id=None, trace_id=None
    ):
        return AgentState(
            run_id=run_id or str(uuid.uuid4()),
            trace_id=trace_id or str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            goal=goal or "回答用户问诊问题",
            original_input=input_text,
            max_steps=config.AGENT_MAX_STEPS,
            timeout_seconds=config.AGENT_TIMEOUT_SECONDS,
        )

    def _prepare(self, input_text, conversation_id, user_id, context, goal, run_id, trace_id):
        state = self.create_state(input_text, conversation_id, user_id, goal, run_id, trace_id)
        state.context = context or ""
        self._states[state.run_id] = state
        return state

    def run(
        self,
        input_text,
        conversation_id=None,
        user_id=None,
        context="",
        goal=None,
        run_id=None,
        trace_id=None,
        **kwargs,
    ):
        state = self._prepare(input_text, conversation_id, user_id, context, goal, run_id, trace_id)
        for _ in self._events(state):
            pass
        return state.final_output or self._build_error_response(state)

    def run_stream(
        self,
        input_text,
        conversation_id=None,
        user_id=None,
        context="",
        goal=None,
        run_id=None,
        trace_id=None,
        **kwargs,
    ):
        state = self._prepare(input_text, conversation_id, user_id, context, goal, run_id, trace_id)
        try:
            for event in self._events(state):
                yield json.dumps(event, ensure_ascii=False)
        finally:
            if state.status == AgentStatus.RUNNING:
                state.interrupt()

    def _events(self, state):
        valid, error = self.policies.validate_input(state.original_input)
        if not valid:
            state.fail("输入无法处理，请重新描述问诊问题。", "INPUT_VALIDATION_ERROR")
            yield {"type": "error", "content": state.error_message, "run_id": state.run_id}
            return
        state.start()
        self.event_bus.publish(RunStartedEvent(state.run_id, state.goal, "[content omitted]"))
        answer, sources, waiting = INSUFFICIENT, [], False
        try:
            # Urgent current symptoms must not wait for memory, retrieval or an LLM.
            flags = urgent_signals(state.original_input or "")
            if flags:
                state.patient = {"is_medical": True, "urgent": True, "red_flags": flags}
                state.task_type = "knowledge_qa"
                answer, state.stop_reason = ESCALATION, "urgent_risk"
                yield {"type": "routed", "task_type": state.task_type, "run_id": state.run_id}
            else:
                if state.conversation_id:
                    yield from self._step(state, "memory_read")
                if self._is_greeting(state.original_input):
                    state.task_type = "chitchat"
                    answer = "你好，我是问诊与护理知识助手。请描述你的症状或想了解的问题。"
                    state.stop_reason = "greeting"
                    yield {"type": "routed", "task_type": state.task_type, "run_id": state.run_id}
                else:
                    yield from self._step(state, "patient_assessment", self._assess)
                    state.task_type = "knowledge_qa"
                    yield {"type": "routed", "task_type": state.task_type, "run_id": state.run_id}
                    answer, sources, waiting = yield from self._loop(state)
        except TimeoutError:
            state.stop_reason = state.stop_reason or "timeout"
            answer = "本轮处理已达到执行上限。" + INSUFFICIENT
        except InterruptedError:
            state.interrupt()
            yield {"type": "error", "content": "本次问诊已中断。", "run_id": state.run_id}
            return
        except Exception:
            # Do not expose SDK exceptions, credentials or patient data in traces.
            logger.warning("Agent run failed; run_id=%s", state.run_id)
            state.fail("问诊处理暂时失败，请稍后重试。", "AGENT_EXECUTION_ERROR")
            self.event_bus.publish(
                RunFailedEvent(state.run_id, state.error_message, state.error_code)
            )
            yield {"type": "error", "content": state.error_message, "run_id": state.run_id}
            return

        if state.status == AgentStatus.INTERRUPTED:
            yield {"type": "error", "content": "本次问诊已中断。", "run_id": state.run_id}
            return
        state.pending_answer = None
        output = {
            "answer": answer,
            "sources": sources,
            "has_sources": bool(sources),
            "task_type": state.task_type,
            "run_id": state.run_id,
            "trace_id": state.trace_id,
            "requires_input": waiting,
            "stop_reason": state.stop_reason,
            "evidence_sufficient": bool(sources),
            "status": "waiting" if waiting else "completed",
        }
        state.final_output = output
        # The business gateway also persists replies. A memory outage must not
        # discard an already verified answer, and no new work starts after budget.
        if state.conversation_id and self._remaining(state) > 0 and not state.is_max_steps_reached:
            try:
                memory_result = yield from self._step(state, "memory_write", self._save_reply)
            except (TimeoutError, RuntimeError):
                output["memory_saved"] = False
            except InterruptedError:
                state.interrupt()
                yield {"type": "error", "content": "本次问诊已中断。", "run_id": state.run_id}
                return
            else:
                output["memory_saved"] = bool(memory_result.get("success"))
        state.final_output = output
        if waiting:
            state.wait()
            state.end_time = time.time()
        else:
            state.complete(output)
        self.event_bus.publish(RunCompletedEvent(state.run_id, output))
        # Emit only verified final text; a rejected draft never reaches the client.
        yield {"type": "sources", "content": sources}
        if waiting:
            yield {"type": "clarification", "content": {"content": answer, "requires_input": True}}
        for index in range(0, len(answer), 32):
            yield {"type": "token", "content": answer[index : index + 32]}
        yield {"type": "end", "content": output}

    def _loop(self, state):
        last_answer_round = -1
        while state.decision_count < config.AGENT_MAX_DECISIONS:
            decision_data = yield from self._step(state, "agent_decision", self._decide)
            state.decision_count += 1
            action = decision_data["action"]
            if action == "ask_user":
                state.stop_reason = "needs_user_input"
                fields = decision_data.get("requested_fields") or state.patient.get(
                    "missing_information"
                )
                fields = fields or ["伴随症状", "既往病史", "正在使用的药物"]
                question = "为了继续评估，请补充：" + "、".join(fields[:3]) + "。"
                return question, [], True
            if action == "escalate":
                state.stop_reason = (
                    "urgent_risk" if state.patient.get("urgent") else "insufficient_evidence"
                )
                return (ESCALATION if state.patient.get("urgent") else INSUFFICIENT), [], False
            if action == "search":
                if len(state.searched_queries) >= config.AGENT_MAX_SEARCHES:
                    state.stop_reason = "search_limit"
                    break
                query = decision_data["query"].strip()
                key = self._query_key(query)
                if not key or key in {self._query_key(q) for q in state.searched_queries}:
                    state.stop_reason = "repeated_query" if key else "invalid_query"
                    break
                state.searched_queries.append(query)
                state.evidence = {}
                result = yield from self._step(
                    state, "knowledge_search", parameters={"query": query}
                )
                yield from self._step(
                    state,
                    "result_evaluation",
                    lambda working, step: self.consultation.evaluate(working, result),
                )
                continue
            if action == "answer":
                if not state.evidence.get("is_sufficient"):
                    # A model cannot bypass the evidence gate by choosing answer.
                    state.stop_reason = "answer_without_evidence"
                    break
                if last_answer_round == len(state.searched_queries):
                    state.stop_reason = "repeated_answer"
                    break
                last_answer_round = len(state.searched_queries)
                yield from self._step(state, "answer_generation", self._draft)
                result = yield from self._step(state, "answer_verification", self._verify)
                if result["passed"]:
                    state.stop_reason = "answered"
                    return result["answer"], result["sources"], False
                state.evidence["is_sufficient"] = False
                state.evidence["missing_aspects"] = ["回答中的结论未通过来源或安全校验"]
                continue
        if not state.stop_reason:
            state.stop_reason = "decision_limit"
        return INSUFFICIENT, [], False

    def _remaining(self, state):
        return state.timeout_seconds - state.elapsed_time

    def _step(self, state, name, operation=None, parameters=None):
        if state.status == AgentStatus.INTERRUPTED:
            raise InterruptedError()
        if self._remaining(state) <= 0:
            raise TimeoutError()
        if state.is_max_steps_reached:
            state.stop_reason = "step_limit"
            raise TimeoutError()
        state.planned_steps.append(name)
        step = state.add_step(self._get_step_type(name), name, parameters or {})
        step.start()
        self.event_bus.publish(
            StepStartedEvent(state.run_id, step.step_id, name, step.step_type.value)
        )
        yield {
            "type": "step_started",
            "step_name": name,
            "step_type": step.step_type.value,
            "step_id": step.step_id,
            "run_id": state.run_id,
        }
        if state.status == AgentStatus.INTERRUPTED:
            raise InterruptedError()
        working = deepcopy(state)
        working_step = working.steps[-1]

        def execute():
            if operation:
                working_step.complete(operation(working, working_step))
            else:
                self.executor.execute_step(working, working_step)
            return working

        try:
            updated = call_with_timeout(
                execute, min(config.AGENT_STEP_TIMEOUT_SECONDS, self._remaining(state))
            )
            if state.status == AgentStatus.INTERRUPTED:
                raise InterruptedError()
            if self._remaining(state) <= 0:
                raise TimeoutError()
            # Commit only completed work. A late worker cannot mutate live state.
            state.__dict__.update(updated.__dict__)
            step = state.steps[-1]
        except Exception as exc:
            step.fail(type(exc).__name__)
            self.event_bus.publish(
                StepFailedEvent(
                    state.run_id, step.step_id, name, step.step_type.value, type(exc).__name__
                )
            )
            yield {"type": "step_failed", "step_name": name, "error": type(exc).__name__}
            raise
        self.event_bus.publish(
            StepCompletedEvent(
                state.run_id,
                step.step_id,
                name,
                step.step_type.value,
                step.output_data,
                step.duration_ms or 0,
            )
        )
        yield {
            "type": "step_completed",
            "step_name": name,
            "step_id": step.step_id,
            "output": step.output_data,
        }
        return step.output_data

    def _assess(self, state, step):
        return self.consultation.assess(state)

    def _decide(self, state, step):
        return self.consultation.decide(state).model_dump()

    def _draft(self, state, step):
        draft = self.consultation.draft(state)
        state.pending_answer = draft.model_dump() if draft else None
        return {"claim_count": len(draft.claims) if draft else 0}

    def _verify(self, state, step):
        draft = AnswerDraft.model_validate(state.pending_answer) if state.pending_answer else None
        result = self.consultation.verify(state, draft)
        state.pending_answer = None
        return result

    def _save_reply(self, state, step):
        saved = self.executor.memory_agent.save_memory(
            state, state.original_input, state.final_output["answer"]
        )
        return {"success": bool(saved)}

    @staticmethod
    def _is_greeting(text):
        return bool(
            re.fullmatch(
                r"\s*(你好|您好|谢谢|感谢|再见|嗨|hello|hi|你是谁)[！!。，,.？?\s]*",
                text or "",
                re.I,
            )
        )

    @staticmethod
    def _query_key(query):
        return re.sub(r"[\W_]+", "", query.casefold())

    @staticmethod
    def _get_step_type(name):
        mapping = {item.value: item for item in StepType}
        mapping.update(
            {
                "patient_assessment": StepType.QUESTION_CLASSIFICATION,
                "agent_decision": StepType.INTENT_RECOGNITION,
                "answer_verification": StepType.RESULT_EVALUATION,
                "identity_answer": StepType.ANSWER_GENERATION,
            }
        )
        return mapping.get(name, StepType.TOOL_CALL)

    @staticmethod
    def _build_error_response(state):
        return {
            "answer": state.error_message or "问诊未完成，请重试。",
            "sources": [],
            "error": True,
            "status": state.status.value,
            "error_code": state.error_code,
        }

    def get_state(self, run_id):
        return self._states.get(run_id)

    def get_all_states(self):
        return dict(self._states)

    def clear_state(self, run_id):
        return self._states.pop(run_id, None) is not None

    def interrupt(self, run_id):
        state = self.get_state(run_id)
        if state and state.status == AgentStatus.RUNNING:
            state.interrupt()
            return True
        return False
